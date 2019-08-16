import sys

sys.path.append('RAMCloud/scripts')
sys.path.append('RAMCloud/bindings/python')

import common
import os

os.environ['LD_LIBRARY_PATH'] = common.obj_dir + ':' + 'RAMCloud-install/lib:' + os.environ['LD_LIBRARY_PATH']
