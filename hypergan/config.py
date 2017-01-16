import hyperchamber as hc
from hypergan.util.ops import *
from hypergan.util.globals import *
from hypergan.util.gan_server import *
from tensorflow.contrib import ffmpeg
import hypergan.util.hc_tf as hc_tf
import hypergan.generators.resize_conv as resize_conv
import hypergan.generators.dense_resize_conv as dense_resize_conv
import hypergan.generators.resize_conv_extra_layer as resize_conv_extra_layer
import hypergan.trainers.adam_trainer as adam_trainer
import hypergan.trainers.rmsprop_trainer as rmsprop_trainer
import hypergan.trainers.slowdown_trainer as slowdown_trainer
import hypergan.trainers.sgd_adam_trainer as sgd_adam_trainer
import hypergan.discriminators.pyramid_discriminator as pyramid_discriminator
import hypergan.discriminators.pyramid_nostride_discriminator as pyramid_nostride_discriminator
import hypergan.discriminators.slim_stride as slim_stride
import hypergan.discriminators.densenet_discriminator as densenet_discriminator
import hypergan.discriminators.fast_densenet_discriminator as fast_densenet_discriminator
import hypergan.discriminators.painters_discriminator as painters_discriminator
import hypergan.encoders.random_encoder as random_encoder
import hypergan.encoders.random_gaussian_encoder as random_gaussian_encoder
import hypergan.encoders.random_combo_encoder as random_combo_encoder
import hypergan.encoders.progressive_variational_encoder as progressive_variational_encoder
import hypergan.samplers.progressive_enhancement_sampler as progressive_enhancement_sampler
import hypergan.samplers.grid_sampler as grid_sampler
import hypergan.regularizers.minibatch_regularizer as minibatch_regularizer
import hypergan.regularizers.moment_regularizer as moment_regularizer
import hypergan.regularizers.progressive_enhancement_minibatch_regularizer as progressive_enhancement_minibatch_regularizer
import hypergan.regularizers.l2_regularizer as l2_regularizer



# Below are sets of configuration options:
# Each time a new random network is started a random set of configuration variables are selected.
# This is useful for hyperparameter search.  If you want to use a specific configuration use --config

def selector(args):
    selector = hc.Selector()
    selector.set('dtype', tf.float32) #The data type to use in our GAN.  Only float32 is supported at the moment

    # Z encoder configuration
    selector.set('encoder', random_combo_encoder.encode_gaussian) # how to encode z

    # Generator configuration
    selector.set("generator.z", 40) # the size of the encoding.  Encoder is set by the 'encoder' property, but could just be a random_uniform
    selector.set("generator", [dense_resize_conv.generator])
    selector.set("generator.z_projection_depth", 512) # Used in the first layer - the linear projection of z
    selector.set("generator.activation", [prelu("g_")]); # activation function used inside the generator
    selector.set("generator.activation.end", [tf.nn.tanh]); # Last layer of G.  Should match the range of your input - typically -1 to 1
    selector.set("generator.fully_connected_layers", 0) # Experimental - This should probably stay 0
    selector.set("generator.final_activation", [tf.nn.tanh]) #This should match the range of your input
    selector.set("generator.resize_conv.depth_reduction", 2) # Divides our depth by this amount every time we go up in size
    selector.set('generator.layer.noise', False) #Adds incremental noise each layer
    selector.set("generator.regularizers.l2.lambda", list(np.linspace(0.1, 1, num=30))) # the magnitude of the l2 regularizer(experimental)
    selector.set("generator.regularizers.layer", [batch_norm_1]) # the magnitude of the l2 regularizer(experimental)
    selector.set('generator.densenet.size', 32)
    selector.set('generator.densenet.layers', 3)
    
    # Trainer configuration
    trainer = adam_trainer # adam works well at 64x64 but doesn't scale
    #trainer = slowdown_trainer # this works at higher resolutions, but is slow and quirky(help wanted)
    #trainer = rmsprop_trainer # this works at higher resolutions, but is slow and quirky(help wanted)
    #trainer = sgd_adam_trainer # This has never worked, but seems like it should
    selector.set("trainer.initializer", trainer.initialize) # TODO: can we merge these variables?
    selector.set("trainer.train", trainer.train) # The training method to use.  This is called every step
    selector.set("trainer.adam.discriminator.lr", 1e-3) #adam_trainer d learning rate
    selector.set("trainer.adam.discriminator.epsilon", 1e-8) #adam epsilon for d
    selector.set("trainer.adam.discriminator.beta1", 0.9) #adam beta1 for d
    selector.set("trainer.adam.discriminator.beta2", 0.999) #adam beta2 for d
    selector.set("trainer.adam.generator.lr", 1e-3) #adam_trainer g learning rate
    selector.set("trainer.adam.generator.epsilon", 1e-8) #adam_trainer g
    selector.set("trainer.adam.generator.beta1", 0.9) #adam_trainer g
    selector.set("trainer.adam.generator.beta2", 0.999) #adam_trainer g
    selector.set("trainer.rmsprop.discriminator.lr", 3e-5) # d learning rate
    selector.set("trainer.rmsprop.generator.lr", 1e-4) # d learning rate
    selector.set('trainer.slowdown.discriminator.d_fake_min', [0.12]) # healthy above this number on d_fake
    selector.set('trainer.slowdown.discriminator.d_fake_max', [0.12001]) # unhealthy below this number on d_fake
    selector.set('trainer.slowdown.discriminator.slowdown', [5]) # Divides speed by this number when unhealthy(d_fake low)
    selector.set("trainer.sgd_adam.discriminator.lr", 3e-4) # d learning rate
    selector.set("trainer.sgd_adam.generator.lr", 1e-3) # g learning rate

    # TODO: cleanup
    selector.set("examples_per_epoch", 30000/4)
    
    # Discriminator configuration
    discriminators = []
    for i in range(1):
        discriminators.append(pyramid_nostride_discriminator.config(layers=5))
    for i in range(1):
        discriminators.append(densenet_discriminator.config(resize=[64,64], layers=4))
    selector.set("discriminators", [discriminators])
    
    # Sampler configuration
    selector.set("sampler", progressive_enhancement_sampler.sample) # this is our sampling method.  Some other sampling ideas include cosine distance or adverarial encoding(not implemented but contributions welcome).
    selector.set("sampler.samples", 3) # number of samples to generate at the end of each epoch

    selector.set('categories', [[]])
    selector.set('categories_lambda', list(np.linspace(.001, .01, num=100)))
    selector.set('category_loss', [False])
    
    # Loss function configuration
    selector.set('g_class_loss', [False])
    selector.set('g_class_lambda', list(np.linspace(0.01, .1, num=30)))
    selector.set('d_fake_class_loss', [False])
    
    selector.set("g_target_prob", list(np.linspace(.65 /2., .85 /2., num=100)))
    selector.set("d_label_smooth", list(np.linspace(0.15, 0.35, num=100)))
    
    # Minibatch configuration TODO move to minibatch
    selector.set("d_kernels", list(np.arange(20, 30)))
    selector.set("d_kernel_dims", list(np.arange(200, 300)))

    # Vae Loss configuration TODO cleanup
    selector.set("adv_loss", [False])
    selector.set("latent_loss", [False])
    selector.set("latent_lambda", list(np.linspace(.01, .1, num=30)))

    return selector

def random(args):
    return selector(args).random_config()