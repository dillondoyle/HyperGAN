import tensorflow as tf
import numpy as np
from scipy.misc import imsave
tensors = {}

#TODO:  This is messy - basically just a global variable system.  Should be refactored to not use this
def set_tensor(name, tensor):
  tensors[name]=tensor

def get_tensor(name, graph=tf.get_default_graph(), isOperation=False):
    return tensors[name]# || graph.as_graph_element(name)


# TODO: Why is this function here?
def plot(config, image, file):
    """ Plot a single CIFAR image."""
    image = np.squeeze(image)
    print(file, image.shape)
    imsave(file, image)

def capped_optimizer(optimizer, lr, loss, vars):
  capped_optimizer = optimizer(lr)
  gvs = capped_optimizer.compute_gradients(loss, var_list=vars)
  def create_cap(grad,var):
    if(grad == None):
        print("Warning: No gradient for variable ",var.name)
        return None
    return (tf.clip_by_value(grad, -1., 1.), var)
  capped_gvs = [create_cap(grad,var) for grad, var in gvs]
  capped_gvs = [x for x in capped_gvs if x != None]
  return capped_optimizer.apply_gradients(capped_gvs)
