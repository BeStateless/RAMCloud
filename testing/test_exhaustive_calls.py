import ramcloud
import cluster_test_utils as ctu

def run_queries():
    rc = ramcloud.RAMCloud()
    rc.connect('zk:169.254.3.1:2181,169.254.3.2:2181,169.254.3.3:2181', 'main')
    rc.create_table('test')
    tid = rc.get_table_id('test')
    while(True):
        versions = []
        values = []
        for ii in range(20):
            key = ('testKey%s'% ii)
            version = 0
            value = ""
            try:
                (value, version) = rc.read(tid, key)
            except:
                value=""
                version=0
            versions.append(version)
            values.append(value)
        for ii in range(20):
            key = ('testKey%s'% ii)
            version = versions[ii]
            if (versions == 0):
                version = None
            newValue = ('%s' % values[ii])
            if len(newValue) >= 9:
                vv = int(newValue[9:])
                vv = vv + 1
                newValue = ('testValue%s' % vv)
            else:
                newValue = 'testValue1'
            # print("key = %s, value = %s, tid=%d, version=%d" % (key, newValue, tid, version))
            # Note: Use version here if you want reject-rules
            rc.write(tid, key, newValue)
