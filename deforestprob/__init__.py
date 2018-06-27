#!/usr/bin/python

# ==============================================================================
# author          :Ghislain Vieilledent
# email           :ghislain.vieilledent@cirad.fr, ghislainv@gmail.com
# web             :https://ghislainv.github.io
# python_version  :2.7
# license         :GPLv3
# ==============================================================================

import os
import matplotlib
if os.environ.get('DISPLAY','') == '':
    print('no display found. Using non-interactive Agg backend')
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from data import country
from miscellaneous import invlogit, make_dir
import plot
from model_binomial_iCAR import model_binomial_iCAR
from sample import sample
from cellneigh import cellneigh
from predict_raster import predict_raster
from predict_raster_binomial_iCAR import predict_raster_binomial_iCAR
from resample_rho import resample_rho
from deforest import deforest
from validation import accuracy_indices, validation
from emissions import emissions
from countpix import countpix

# End
