#!/usr/bin/python

import argparse
import datetime
# import threading
# import time

class Fault:
    def stateless(self):
        raise NotImplementedError

    def stateful(self):
        raise NotImplementedError

    def deterministic(self):
        raise NotImplementedError


class Ceph(Fault):
    def stateless(self, target):
        print "ceph stateless"

    def stateful(self):
        print "ceph stateful"

    def deterministic(self):
        print "ceph deterministic"

class Node:
    def __init__(self, node_type, node_ip, node_id):
        self.type = node_type
        self.ip = node_ip
        self.id = node_id 

class Deployment:
    def __init__(self, filename):
        """ Takes in a deployment config file 
        """
        self.nodes = []
        with open('config.yaml', 'r') as f:
            config = yaml.load(f)
        for node_index in range(config['numnodes']):
            current_node = config['node' + node_index]
            nodes.append(Node(current_node['type'], current_node['ip'], current_node['id']))

# global var for log file
log = open('FaultInjector.log', 'a')

def main():

    # start injector
    log.write('{:%Y-%m-%d %H:%M:%S} Fault Injector Started\n'.format(datetime.datetime.now()))

    # create argument parser
    parser = argparse.ArgumentParser(description='Fault Injector')
    parser.add_argument('-d','--deterministic', help='injector will follow the list of tasks in the file specified', action='store', nargs=1, dest='filepath')
    parser.add_argument('-sf','--stateful', help='injector will run in stateful random mode', required=False, action='store_true')
    parser.add_argument('-sl','--stateless', help='injector will run in stateless random mode', required=False, action='store_true')
    args = parser.parse_args()

    # check mode
    if args.filepath:
        deterministic_start()
    elif args.stateful:
        stateful_start()
    elif args.stateless:
        stateless_start()
    else:
        print "No Mode Chosen"

    # end injector
    log.write('{:%Y-%m-%d %H:%M:%S} Fault Injector Stopped\n'.format(datetime.datetime.now()))
    log.close()


def deterministic_start():
    print "det"

def stateful_start():
    print "sf"

def stateless_start():
    print "sl"






#   print "main"
#   t1 = threading.Thread(target=thread1)
#   t2 = threading.Thread(target=thread2)
#   t3 = threading.Thread(target=thread3)
#   t1.start()
#   t2.start()
#   t3.start()

#   t1.join()
#   t2.join()
#   t3.join()

#   print "done"

# def thread1():
#   time.sleep(5)
#   print "im the thread1"
#   time.sleep(5)
#   print "thread1 again"

# def thread2():
#   time.sleep(5)
#   print "im the thread2"
#   time.sleep(5)
#   print "thread2 again"

# def thread3():
#   time.sleep(5)
#   print "im the thread3"
#   time.sleep(5)
#   print "thread3 again"


if __name__ == "__main__":
    main()
