#!/usr/bin/python

import argparse
import datetime
import os
import random
import re
import signal
import subprocess
import sys
import threading
import time
import yaml
import string


class Fault:
    """ Template class to make your own fault
    add an instance of your fault to the list of plugins in main
    """

    def __init__(self, deployment):
        self.deployment = deployment
        # create a list of fault functions
        self.functions = []

    def __repr__(self):
        raise NotImplementedError

    def stateless(self, deterministic_file, timelimit):
        raise NotImplementedError

    def stateful(self, deterministic_file, timelimit):
        raise NotImplementedError

    def deterministic(self, args):
        raise NotImplementedError

    def check_exit_signal(self):
        if stopper.is_set():
            sys.exit(0)

    # Write fault functions below --------------------------------------------- 

    def template_fault(self):
        print 'template_fault was called'

        start_time = datetime.datetime.now() - global_starttime
        # Call to playbook goes here
        # Delay x amount of time
        end_time = datetime.datetime.now() - global_starttime
        # Placeholder fault function
        return [start_time, end_time, 'Exit Status']  # Placeholder exit status variable


class Node_fault(Fault):
    def __init__(self, deployment):
        Fault.__init__(self, deployment)
        # create a list of fault functions
        self.functions = [self.node_kill_fault]

    def __repr__(self):
        return 'Node_fault'

    def stateless(self, deterministic_file, timelimit):
        # Infinite loop for indefinite mode
        while timelimit is None:
            result = random.choice(self.functions)()
            if result is None:
                continue
            log.write(
                '{:%Y-%m-%d %H:%M:%S} [stateless-mode] executing ' + str(result) + '\n'.format(datetime.datetime.now()))
            deterministic_file.write(self.__repr__() + ' | ' + str(result[0]) +
                                     ' | ' + str(result[1]) + ' | ' + str(result[2]) +
                                     ' | ' + str(result[3]) + ' | ' + str(result[4]) +
                                     ' | ' + str(result[5]) + '\n')
            deterministic_file.flush()
            os.fsync(deterministic_file.fileno())
            # check for exit signal
            self.check_exit_signal()

        # Standard runtime loop
        timeout = time.time() + 60 * timelimit
        while time.time() < timeout:
            result = random.choice(self.functions)()
            if result is None:
                continue
            log.write(
                '{:%Y-%m-%d %H:%M:%S} [stateless-mode] executing ' + str(result) + '\n'.format(datetime.datetime.now()))
            deterministic_file.write(self.__repr__() + ' | ' + str(result[0]) +
                                     ' | ' + str(result[1]) + ' | ' + str(result[2]) +
                                     ' | ' + str(result[3]) + ' | ' + str(result[4]) +
                                     ' | ' + str(result[5]) + '\n')
            deterministic_file.flush()
            os.fsync(deterministic_file.fileno())
            # check for exit signal
            self.check_exit_signal()

        log.write('{:%Y-%m-%d %H:%M:%S} [stateless-mode] time out reached\n'.format(datetime.datetime.now()))

    def deterministic(self, args):

        # convert endtime to seconds
        l = args[3].split(':')
        secs = int(l[0]) * 3600 + int(l[1]) * 60 + int(float(l[2]))

        # find target node (if it exists)
        target = None
        for node in self.deployment.nodes:
            if node[0].ip.strip() == args[2].strip():
                target = node
                break

        # wait until start time
        while time.time() < int(global_starttime.strftime('%s')) + secs:
            self.check_exit_signal()
            time.sleep(1)

        # call fault
        if args[1] == 'node-kill-fault':
            log.write('{:%Y-%m-%d %H:%M:%S} [deterministic-mode] executing node-kill-fault at {0}{1}'.format(
                str(target[0].ip), '\n'.format(datetime.datetime.now())))
            self.det_node_kill_fault(target, int(args[5]))
        else:
            print 'no matching function found'

    # Write fault functions below ---------------------------------------------

    def node_kill_fault(self):
        # chose node to fault
        target_node = random.choice(self.deployment.nodes)
        while target_node[0].occupied:
            target_node = random.choice(self.deployment.nodes)

        target_node[0].occupied = True

        # check for exit signal
        self.check_exit_signal()

        # create tmp file for playbook
        crash_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        restore_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

        # modify crash playbook
        with open('playbooks/system-crash.yml') as f:
            crash_config = yaml.load(f)
            crash_config[0]['hosts'] = target_node[0].ip
            for task in crash_config[0]['tasks']:
                if task['name'] == 'Power off server':
                    task['local_action'] = 'shell . ~/stackrc && nova stop ' + target_node[0].id

        with open('playbooks/' + crash_filename, 'w') as f:
            yaml.dump(crash_config, f, default_flow_style=False)

        # modify restore playbook
        with open('playbooks/system-restore.yml') as f:
            restore_config = yaml.load(f)
            restore_config[0]['hosts'] = target_node[0].ip
            for task in restore_config[0]['tasks']:
                if task['name'] == 'Power on server':
                    task['local_action'] = 'shell . ~/stackrc && nova start ' + target_node[0].id
                if task['name'] == 'waiting 30 secs for server to come back':
                    task['local_action'] = 'wait_for host=' + target_node[
                        0].ip + ' port=22 state=started delay=30 timeout=120'

        with open('playbooks/' + restore_filename, 'w') as f:
            yaml.dump(restore_config, f, default_flow_style=False)

        # check for exit signal
        self.check_exit_signal()

        # crash system
        start_time = datetime.datetime.now() - global_starttime
        subprocess.call('ansible-playbook playbooks/' + crash_filename, shell=True)
        log.write('{:%Y-%m-%d %H:%M:%S} [node-kill-fault] Node killed\n'.format(datetime.datetime.now()))

        # wait

        # FIX ME FOR PRODUCTION
        downtime = random.randint(15, 45)  # Picks a random integer such that: 15 <= downtime <= 45

        log.write('{:%Y-%m-%d %H:%M:%S} [node-kill-fault] waiting ' +
                  str(downtime) + ' minutes before restoring \
                      \n'.format(datetime.datetime.now()))

        counter = downtime
        while counter > 0:
            # check for exit signal
            self.check_exit_signal()
            time.sleep(5)  # 60)
            counter -= 1

        # restore system
        subprocess.call('ansible-playbook playbooks/' + restore_filename, shell=True)
        log.write('{:%Y-%m-%d %H:%M:%S} [node-kill-fault] Node restored\n'.format(datetime.datetime.now()))
        end_time = datetime.datetime.now() - global_starttime

        target_node[0].occupied = False

        # clean up tmp files
        os.remove(os.path.join('playbooks/', crash_filename))
        os.remove(os.path.join('playbooks/', restore_filename))

        return ['node-kill-fault', target_node[0].ip, start_time, end_time, downtime, False]

    def det_node_kill_fault(self, target_node, downtime):
        target_node[0].occupied = True

        # check for exit signal
        self.check_exit_signal()

        # create tmp file for playbook
        crash_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        restore_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

        # modify crash playbook
        with open('playbooks/system-crash.yml') as f:
            crash_config = yaml.load(f)
            crash_config[0]['hosts'] = target_node[0].ip
            for task in crash_config[0]['tasks']:
                if task['name'] == 'Power off server':
                    task['local_action'] = 'shell . ~/stackrc && nova stop ' + target_node[0].id

        with open('playbooks/' + crash_filename, 'w') as f:
            yaml.dump(crash_config, f, default_flow_style=False)

        # modify restore playbook
        with open('playbooks/system-restore.yml') as f:
            restore_config = yaml.load(f)
            restore_config[0]['hosts'] = target_node[0].ip
            for task in restore_config[0]['tasks']:
                if task['name'] == 'Power on server':
                    task['local_action'] = 'shell . ~/stackrc && nova start ' + target_node[0].id
                if task['name'] == 'waiting 30 secs for server to come back':
                    task['local_action'] = 'wait_for host=' + target_node[
                        0].ip + ' port=22 state=started delay=30 timeout=120'

        with open('playbooks/' + restore_filename, 'w') as f:
            yaml.dump(restore_config, f, default_flow_style=False)

        # check for exit signal
        self.check_exit_signal()

        # crash system
        subprocess.call('ansible-playbook playbooks/' + crash_filename, shell=True)
        log.write('{:%Y-%m-%d %H:%M:%S} [node-kill-fault] Node killed\n'.format(datetime.datetime.now()))

        # wait
        log.write('{:%Y-%m-%d %H:%M:%S} [node-kill-fault] waiting ' +
                  str(downtime) + ' minutes before restoring \
                      \n'.format(datetime.datetime.now()))
        while downtime > 0:
            # check for exit signal
            self.check_exit_signal()
            time.sleep(60)
            downtime -= 1

        # restore system
        subprocess.call('ansible-playbook playbooks/' + restore_filename, shell=True)
        log.write('{:%Y-%m-%d %H:%M:%S} [node-kill-fault] Node restored\n'.format(datetime.datetime.now()))

        target_node[0].occupied = False

        # clean up tmp files
        os.remove(os.path.join('playbooks/', crash_filename))
        os.remove(os.path.join('playbooks/', restore_filename))


class Ceph(Fault):
    def __init__(self, deployment):
        Fault.__init__(self, deployment)
        # create a list of fault functions
        self.functions = [self.osd_service_fault, self.mon_service_fault]

    def __repr__(self):
        return 'Ceph'

    def stateful(self, deterministic_file, timelimit):
        """ func that will be set up on a thread
            will write to a shared (all stateful threads will share) log for deterministic mode
            will take a timelimit or run indefinetly till ctrl-c
            will do things randomly (pick node to fault and timing)
        """
        print 'Beginning Ceph Stateful Mdode'

        thread_count = self.deployment.min_replication_size + 1

        fault_threads = []

        # create threads
        for i in range(thread_count):
            thread = threading.Thread(target=self.fault_thread, args=(deterministic_file, timelimit))
            threads.append(thread)
            fault_threads.append(thread)

        # start all threads
        for thread in fault_threads:
            thread.start()
            self.check_exit_signal()
            time.sleep(60)  # Limit threads to starting one per minute

        # wait for all threads to end
        not_done = True
        while not_done:
            not_done = False
            for thread in fault_threads:
                if thread.isAlive():
                    not_done = True
            # check for exit signal
            self.check_exit_signal()
            time.sleep(1)

    def deterministic(self, args):
        """ func that will be set up on a thread
            will take a start time, end time and waiting times (time between fault and restore)
            will take specific node/osd to fault (ip or uuid)
            will run until completion
        """

        # convert endtime to seconds
        l = args[3].split(':')
        secs = int(l[0]) * 3600 + int(l[1]) * 60 + int(float(l[2]))

        # find target node (if it exists)
        target = None
        for node in self.deployment.nodes:
            if node[0].ip.strip() == args[2].strip():
                target = node
                break

        # wait until start time
        while time.time() < int(global_starttime.strftime('%s')) + secs:
            self.check_exit_signal()
            time.sleep(1)

        # call fault
        if args[1] == 'ceph-osd-fault':
            log.write('{:%Y-%m-%d %H:%M:%S} [deterministic-mode] executing osd-service-fault at ' + str(
                target[0]) + '\n'.format(datetime.datetime.now()))
            self.det_service_fault(target, 'osd', int(args[5]), args[6])
        elif args[1] == 'ceph-mon-fault':
            log.write('{:%Y-%m-%d %H:%M:%S} [deterministic-mode] executing mon-service-fault at ' + str(
                target[0]) + '\n'.format(datetime.datetime.now()))
            self.det_service_fault(target, 'mon', int(args[5]), args[6])
        else:
            print 'no matching function found'

    # check_health is no longer used, may remove in the future
    """
    def check_health(self):
        #   Looks at a random functioning controller node
        #   and checks the status of the ceph cluster returning
        #   True if it's healthy
        
        controllers = []
        for node in self.deployment.nodes:
            if 'control' in node.type:
                controllers.append(node)
        if len(controllers) == 0:
            print '[check_health] warning: no controller found in deployment'
            return False

        target_node = random.choice(controllers)
        host = target_node.ip
        response = subprocess.call(['ping', '-c', '5', '-W', '3', host],
                               stdout=open(os.devnull, 'w'),
                               stderr=open(os.devnull, 'w'))
        while response != 0:
            print '[check_health] could not connect to node @' +  \
                    target_node.ip + ', trying another after 20 seconds...'
            target_node = random.choice(controllers)
            host = target_node.ip
            time.sleep(20) # Wait 20 seconds to give nodes time to recover 
            response = subprocess.call(['ping', '-c', '5', '-W', '3', host],
                               stdout=open(os.devnull, 'w'),
                               stderr=open(os.devnull, 'w'))

        command = 'sudo ceph -s | grep health'
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username='heat-admin')
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
        response = str(ssh_stdout.readlines())
        return False if re.search('HEALTH_OK', response, flags=0) == None else True
    """

    # Write fault functions below --------------------------------------------- 

    def fault_thread(self, deterministic_file, timelimit):

        print "Thread Started"

        # Infinite loop for indefinite mode
        while timelimit is None:
            result = random.choice(self.functions)()
            if result is None:
                continue

            self.print_status()

            # Add space if ip is short
            if len(result[1]) == 12:
                result[1] = result[1] + '  '
            elif len(result[1]) == 13:
                result[1] = result[1] + ' '

            deterministic_file.write(self.__repr__() + ' | ' + str(result[0]) +
                                     ' | ' + str(result[1]) + ' | ' + str(result[2]) +
                                     ' | ' + str(result[3]) + ' | ' + str(result[4]) +
                                     ' | ' + str(result[5]) + '\n')
            deterministic_file.flush()
            os.fsync(deterministic_file.fileno())
            # check for exit signal
            self.check_exit_signal()

        # Standard runtime loop
        timeout = time.time() + 60 * timelimit
        while time.time() < timeout:
            # Calls a fault function and stores the results
            result = random.choice(self.functions)()
            if result is None:
                continue

            self.print_status()

            # Add space if ip is short
            if len(result[1]) == 12:
                result[1] = result[1] + '  '
            elif len(result[1]) == 13:
                result[1] = result[1] + ' '

            deterministic_file.write(self.__repr__() + ' | ' + str(result[0]) +
                                     ' | ' + str(result[1]) + ' | ' + str(result[2]) +
                                     ' | ' + str(result[3]) + ' | ' + str(result[4]) +
                                     ' | ' + str(result[5]) + '\n')
            deterministic_file.flush()
            os.fsync(deterministic_file.fileno())
            # check for exit signal
            self.check_exit_signal()

    def osd_service_fault(self):
        """ Kills a random osd service specified on a random ceph node
            or osd-compute node
        """
        candidate_nodes = []
        for node in self.deployment.nodes:
            if self.deployment.hci:
                if 'osd' in node[0].type:
                    candidate_nodes.append(node)
            elif 'ceph' in node[0].type:
                candidate_nodes.append(node)

        # check for exit signal
        self.check_exit_signal()

        target_node = random.choice(candidate_nodes)
        host = target_node[0].ip
        response = subprocess.call(['ping', '-c', '5', '-W', '3', host],
                                   stdout=open(os.devnull, 'w'),
                                   stderr=open(os.devnull, 'w'))

        # Count the number of downed osds
        osds_occupied = 0
        for osd in self.deployment.osds:
            if not osd:  # If osd is off
                osds_occupied += 1

        # Pick a random osd
        target_osd = random.choice(target_node[1])

        # keeps track of how many times the while loop has been executed so it can break after
        # a set amount
        retries = 0

        # node unreachable, target osd is being used, or the number of osds down >= the limit
        while response != 0 or (not self.deployment.osds[target_osd]) or (
                    osds_occupied >= self.deployment.min_replication_size - 1):
            # exit if loop has executed 3 times already
            if retries > 3:
                return

            print response, not self.deployment.osds[target_osd], osds_occupied >= self.deployment.min_replication_size
            if osds_occupied >= self.deployment.min_replication_size - 1:
                print 'osd limit reached'
                log.write(
                    '{:%Y-%m-%d %H:%M:%S} [ceph-osd-fault] osd limit reached, waiting to fault another\n'.format(
                        datetime.datetime.now()))
            else:
                print '[ceph-osd-fault] Target osd down (osd-' + str(target_osd) + ') at IP: ' + str(target_node[
                                                                                                         0].ip) + ', trying to find acceptable node'
                log.write(
                    '{:%Y-%m-%d %H:%M:%S} [ceph-osd-fault] Target osd down, trying to find acceptable node\n'.format(
                        datetime.datetime.now()))
            retries += 1
            target_node = random.choice(candidate_nodes)
            host = target_node[0].ip
            time.sleep(1)
            response = subprocess.call(['ping', '-c', '5', '-W', '3', host],
                                       stdout=open(os.devnull, 'w'),
                                       stderr=open(os.devnull, 'w'))

            # Count the number of downed osds
            osds_occupied = 0
            for osd in self.deployment.osds:
                if not osd:  # If osd is off
                    osds_occupied += 1

            # Pick a random osd
            target_osd = random.choice(target_node[1])

            # check for exit signal
            self.check_exit_signal()

        target_node[0].occupied = True  # Mark node as being used

        # create tmp file for playbook
        crash_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        restore_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

        with open('playbooks/ceph-service-crash.yml') as f:
            config = yaml.load(f)
            config[0]['hosts'] = host
            for task in config[0]['tasks']:
                if task['name'] == 'Stopping ceph service':
                    task['shell'] = 'systemctl stop ceph-osd@' + str(target_osd)
        with open('playbooks/' + crash_filename, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        with open('playbooks/ceph-service-restore.yml') as f:
            config = yaml.load(f)
            config[0]['hosts'] = host
            for task in config[0]['tasks']:
                if task['name'] == 'Restoring ceph service':
                    task['shell'] = 'systemctl start ceph-osd@' + str(target_osd)

        with open('playbooks/' + restore_filename, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        # check for exit signal
        self.check_exit_signal()

        # Fault
        print '[ceph-osd-fault] executing fault on osd-' + str(target_osd)
        self.deployment.osds[target_osd] = False
        start_time = datetime.datetime.now() - global_starttime
        subprocess.call('ansible-playbook playbooks/' + crash_filename, shell=True)

        # Wait
        downtime = random.randint(1, 5)  # 15, 45)  # Picks a random integer such that: 15 <= downtime <= 45
        log.write('{:%Y-%m-%d %H:%M:%S} [ceph-osd-fault] waiting ' +
                  str(downtime) + ' minutes before introducing OSD again' +
                  '\n'.format(datetime.datetime.now()))
        print '[ceph-osd-fault] waiting ' + str(downtime) + ' minutes before restoring osd-' + str(target_osd)
        time.sleep(downtime * 60)

        # Restore
        subprocess.call('ansible-playbook playbooks/' + restore_filename, shell=True)
        log.write('{:%Y-%m-%d %H:%M:%S} [ceph-osd-fault] restoring osd\n'.format(datetime.datetime.now()))
        self.deployment.osds[target_osd] = True
        end_time = datetime.datetime.now() - global_starttime
        target_node[0].occupied = False  # Free up the node

        # clean up tmp files
        os.remove(os.path.join('playbooks/', crash_filename))
        os.remove(os.path.join('playbooks/', restore_filename))

        return ['ceph-osd-fault', target_node[0].ip, start_time, end_time, downtime, target_osd]

    def mon_service_fault(self):
        candidate_nodes = []
        self.deployment.mons_available = 0
        for node in self.deployment.nodes:
            if 'control' in node[0].type:
                candidate_nodes.append(node)
                if node[2]:
                    self.deployment.mons_available += 1

        if self.deployment.mons_available <= 1:
            print "1 or less monitors active, not faulting..."
            return

        target_node = random.choice(candidate_nodes)
        host = target_node[0].ip
        response = subprocess.call(['ping', '-c', '5', '-W', '3', host],
                                   stdout=open(os.devnull, 'w'),
                                   stderr=open(os.devnull, 'w'))

        # node unreachable
        while response != 0:
            target_node = random.choice(candidate_nodes)
            host = target_node[0].ip
            time.sleep(1)  # Wait 20 seconds to give nodes time to recover
            print '[ceph-mon-fault] Target node down, trying to find acceptable node'
            log.write('{:%Y-%m-%d %H:%M:%S} [ceph-mon-fault] Target node down, trying to find acceptable node\n'.format(
                datetime.datetime.now()))
            response = subprocess.call(['ping', '-c', '5', '-W', '3', host],
                                       stdout=open(os.devnull, 'w'),
                                       stderr=open(os.devnull, 'w'))

            self.deployment.mons_available = 0
            for node in self.deployment.nodes:
                if 'control' in node[0].type:
                    candidate_nodes.append(node)
                    if node[2]:
                        self.deployment.mons_available += 1
            if self.deployment.mons_available <= 1:
                return

            # check for exit signal
            self.check_exit_signal()

        target_node[0].occupied = True

        # create tmp file for playbook
        crash_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        restore_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

        with open('playbooks/ceph-service-crash.yml') as f:
            config = yaml.load(f)
            config[0]['hosts'] = host
            for task in config[0]['tasks']:
                if task['name'] == 'Stopping ceph service':
                    task['shell'] = 'systemctl stop ceph-mon.target'
        with open('playbooks/' + crash_filename, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        with open('playbooks/ceph-service-restore.yml') as f:
            config = yaml.load(f)
            config[0]['hosts'] = host
            for task in config[0]['tasks']:
                if task['name'] == 'Restoring ceph service':
                    task['shell'] = 'systemctl start ceph-mon.target'

        with open('playbooks/' + restore_filename, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        # check for exit signal
        self.check_exit_signal()

        print '[ceph-mon-fault] executing fault on a controller node'
        self.deployment.mons_available -= 1
        start_time = datetime.datetime.now() - global_starttime
        target_node[2] = False
        subprocess.call('ansible-playbook playbooks/' + crash_filename, shell=True)
        downtime = random.randint(1, 5)  # 15, 45)  # Picks a random integer such that: 15 <= downtime <= 45
        log.write('{:%Y-%m-%d %H:%M:%S} [ceph-mon-fault] waiting ' +
                  str(downtime) + ' minutes before introducing monitor back' +
                  '\n'.format(datetime.datetime.now()))
        print '[ceph-mon-fault] waiting ' + str(downtime) + ' minutes before restoring monitor'
        time.sleep(downtime * 60)
        subprocess.call('ansible-playbook playbooks/' + restore_filename, shell=True)
        log.write('{:%Y-%m-%d %H:%M:%S} [ceph-mon-fault] restoring monitor\n'.format(datetime.datetime.now()))
        self.deployment.mons_available += 1
        target_node[2] = True
        end_time = datetime.datetime.now() - global_starttime
        target_node[0].occupied = False  # Free up the node

        # clean up tmp files
        os.remove(os.path.join('playbooks/', crash_filename))
        os.remove(os.path.join('playbooks/', restore_filename))

        return ['ceph-mon-fault', target_node[0].ip, start_time, end_time, downtime, 'Mon Fault Placeholder']

        # Deterministic fault functions below ---------------------------------------------

    def det_service_fault(self, target_node, fault_type, downtime, additional_info):
        """ Called by ceph determinisic function
            'fault type' so far is either 'osd' or 'mon'
            'additional_info' used differently depending on the fault type
        """

        # check for exit signal
        self.check_exit_signal()

        host = target_node[0].ip
        response = subprocess.call(['ping', '-c', '5', '-W', '3', host],
                                   stdout=open(os.devnull, 'w'),
                                   stderr=open(os.devnull, 'w'))

        # check for exit signal
        self.check_exit_signal()

        # Make sure target node is reachable 
        if response != 0:
            print '[det_service_fault] error: target node unreachable, \
                    exiting fault function'
            return None

        target_node[0].occupied = True  # Mark node as being used

        # create tmp file for playbook
        crash_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        restore_filename = 'tmp_' + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5))

        with open('playbooks/ceph-service-crash.yml') as f:
            config = yaml.load(f)
            config[0]['hosts'] = host
            if fault_type == 'osd':
                for task in config[0]['tasks']:
                    if task['name'] == 'Stopping ceph service':
                        task['shell'] = 'systemctl stop ceph-osd.' + additional_info
            else:
                for task in config[0]['tasks']:
                    if task['name'] == 'Stopping ceph service':
                        task['shell'] = 'systemctl stop ceph-mon.target'

        with open('playbooks/' + crash_filename, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        # check for exit signal
        self.check_exit_signal()

        with open('playbooks/ceph-service-restore.yml') as f:
            config = yaml.load(f)
            config[0]['hosts'] = host
            if fault_type == 'osd':
                for task in config[0]['tasks']:
                    if task['name'] == 'Restoring ceph service':
                        task['shell'] = 'systemctl start ceph-osd.' + additional_info
            else:
                for task in config[0]['tasks']:
                    if task['name'] == 'Restoring ceph service':
                        task['shell'] = 'systemctl start ceph-mon.target'
        with open('playbooks/' + restore_filename, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        # check for exit signal
        self.check_exit_signal()

        print '[det_service_fault] executing ' + fault_type + ' fault at ' + host
        subprocess.call('ansible-playbook playbooks/' + crash_filename, shell=True)
        log.write('{:%Y-%m-%d %H:%M:%S} [det-service-fault] waiting ' + str(downtime) +
                  ' minutes before restoring\n'.format(datetime.datetime.now()))

        while downtime > 0:
            # check for exit signal
            self.check_exit_signal()
            time.sleep(60)
            downtime -= 1

        subprocess.call('ansible-playbook playbooks/' + restore_filename, shell=True)
        target_node[0].occupied = False  # Free up the node
        # clean up tmp files
        os.remove(os.path.join('playbooks/', crash_filename))
        os.remove(os.path.join('playbooks/', restore_filename))

        print '[det_service_fault] deterministic step completed'

        return True

    def print_status(self):
        osds_occupied = 0
        for osd in self.deployment.osds:
            if not osd:  # If osd is off
                osds_occupied += 1

        self.deployment.mons_available = 0
        for node in self.deployment.nodes:
            if 'control' in node[0].type:
                if node[2]:
                    self.deployment.mons_available += 1

        print "+----------------------\n" \
              "|Current Status:\n" \
              "|----------------------\n" \
              "|osds active: " + str(self.deployment.num_osds - osds_occupied) + '/' + str(self.deployment.num_osds) + '\n' \
              "|monitors active: " + str(self.deployment.mons_available) + '/' + str(self.deployment.num_mons) +'\n' \
              "+----------------------"


class Node:
    def __init__(self, node_type, node_ip, node_id):
        self.type = node_type
        self.ip = node_ip
        self.id = node_id
        self.occupied = False


class Deployment:
    def __init__(self, filename):
        """ Takes in a deployment config file and parses it for the
            deployment configuration 
        """
        self.nodes = []

        hosts = open('hosts', 'w')

        with open(filename, 'r') as f:
            config = yaml.load(f)

            if config is None:
                sys.exit('Error: config.yaml is empty, please fill it out manually or try running setup.py')
            if config['deployment']['num_nodes'] == 0:
                sys.exit('Error: config.yaml is is missing node information, cannot continue')

            # Check for a Ceph deployment
            ceph_deployment = 'ceph' in config

            # Initialize ceph-specific fields
            if ceph_deployment:
                self.num_osds = 0
                self.num_mons = 0
                self.mons_available = 0

            # The 'nodes' list contains Node instances inside of lists with which you 
            # can append any data required for your plugins 
            for node_id in config['deployment']['nodes']:
                # Fill hosts file with IPs
                hosts.write((config['deployment']['nodes'][node_id]['node_ip']) + '\n')

                self.nodes.append([Node(config['deployment']['nodes'][node_id]['node_type'],
                                        config['deployment']['nodes'][node_id]['node_ip'], node_id)])

                self.hci = config['deployment']['hci']
                self.containerized = config['deployment']['containerized']
                self.num_nodes = config['deployment']['num_nodes']
                if ceph_deployment:
                    # Each node in the list of nodes is now a list which holds the following:
                    # [Node Object, List of OSDs, Controller Available (boolean)]
                    self.nodes[-1].append(config['deployment']['nodes'][node_id]['osds'])
                    self.nodes[-1].append(True) if 'control' in config['deployment']['nodes'][node_id]['node_type'] \
                        else self.nodes[-1].append(False)
                    self.num_osds += config['deployment']['nodes'][node_id]['num_osds']
                    if 'control' in config['deployment']['nodes'][node_id]['node_type']:
                        self.num_mons += 1

            if ceph_deployment:
                self.min_replication_size = config['ceph']['minimum_replication_size']
                self.osds = [True for osd in range(self.num_osds)]  # Set all osds to 'on' aka True


# global var for start time of program
global_starttime = datetime.datetime.now()

# global var for log file
log = open('FaultInjector.log', 'a')

# global list of all plugins
plugins = []

# global list of threads
threads = []

# global exit signal for threads
stopper = threading.Event()


def main():
    deployment = Deployment('config.yaml')

    # create list of all plugins and one node_fault instance
    plugins.append(Ceph(deployment))
    plugins.append(Node_fault(deployment))
    # plugins.append()
    node_fault = Node_fault(deployment)

    # signal handler to restore everything to normal
    signal.signal(signal.SIGINT, signal_handler)

    # start injector
    log.write('{:%Y-%m-%d %H:%M:%S} Fault Injector Started\n'.format(datetime.datetime.now()))

    # create argument parser
    parser = argparse.ArgumentParser(description='Fault Injector')
    parser.add_argument('-d', '--deterministic', help='injector will follow the \
                         list of tasks in the file specified', action='store',
                        nargs=1, dest='filepath')
    parser.add_argument('-sf', '--stateful', help='injector will run in stateful \
                        random mode', required=False, action='store_true')
    parser.add_argument('-sl', '--stateless', help='injector will run in stateless \
                        mode with specified number of faults', required=False,
                        type=int, nargs=1, dest='numfaults')
    parser.add_argument('-t', '--timelimit', help='timelimit for injector to run \
                         (mins)', required=False, type=int, metavar='\b')
    args = parser.parse_args()

    # check mode
    if args.filepath:
        if args.timelimit:
            print 'Time Limit not applicable in deterministic mode'
        deterministic_start(args.filepath)
    elif args.stateful:
        stateful_start(args.timelimit)
    elif args.numfaults:
        stateless_start(args.timelimit, node_fault, args.numfaults[0])
    else:
        print 'No Mode Chosen'

    # end injector
    log.write('{:%Y-%m-%d %H:%M:%S} Fault Injector Stopped\n'.format(datetime.datetime.now()))
    log.close()


def deterministic_start(filepath):
    """ func that will read deterministic log
        will create all threads (one per entry in log) and spawn them
        will wait for all threads to complete
    """
    log.write('{:%Y-%m-%d %H:%M:%S} Deterministic Mode Started\n'.format(datetime.datetime.now()))

    # open file
    with open(filepath[0]) as f:
        # read line by line
        for line in f:
            # break into list
            words = line.strip('| ').split(' | ')

            # find matching plugin
            for plugin in plugins:
                if plugin.__repr__() == words[0].strip(' '):
                    # create thread
                    threads.append(threading.Thread(target=plugin.deterministic, args=(words,)))

    # start all threads
    for thread in threads:
        thread.start()
    # wait for all threads to end
    not_done = True
    while not_done:
        not_done = False
        for thread in threads:
            if thread.isAlive():
                not_done = True
        time.sleep(1)


def stateful_start(timelimit):
    """ func that will create a thread for every plugin
        will create a deterministci file that will be passed to every thread
        will pass all threads the timelimit (could be infiniety)
        will spawn all threads
        will wait for all threads to compplete or for ctrl-c
    """
    log.write('{:%Y-%m-%d %H:%M:%S} Stateful Mode Started\n'.format(datetime.datetime.now()))
    print 'Stateful'

    if timelimit is None:
        log.write('{:%Y-%m-%d %H:%M:%S} Indefinite Timelimit\n'.format(datetime.datetime.now()))
        print 'Indefinite Time Limit: press ctrl-c to quit at any time'
    else:
        log.write('{:%Y-%m-%d %H:%M:%S} {} Minute Timelimit\n'.format(datetime.datetime.now(), timelimit))
        print '{} Minute Time Limit'.format(timelimit)

        # writes a file that can feed into a deterministic run
    dir_path = os.path.join(os.path.dirname(__file__), 'deterministic-runs/')
    # create directory if it doesn't exist
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    deterministic_filename = dir_path + str(global_starttime).replace(' ', '_') + '-run.txt'
    deterministic_file = open(deterministic_filename, 'w')

    # create thread for every plugin
    stateful_threads = []

    for plugin in plugins:
        if plugin.__repr__() != 'Node_fault':
            thread = threading.Thread(target=plugin.stateful, args=(deterministic_file, timelimit))
            stateful_threads.append(thread)
            threads.append(thread)

    # start all threads
    for thread in stateful_threads:
        thread.start()

    # wait for all threads to end
    not_done = True
    while not_done:
        not_done = False
        for thread in threads:
            if thread.isAlive():
                not_done = True
        time.sleep(1)


def stateless_start(timelimit, node_fault, numfaults):
    """ func that will read from stateless config
        will run Node_fault statless mode on main thread
        will pass the timelimit (could be infiniety)
    """
    log.write('{:%Y-%m-%d %H:%M:%S} Stateless Mode Started\n'.format(datetime.datetime.now()))

    if timelimit is None:
        log.write('{:%Y-%m-%d %H:%M:%S} Indefinite Time Limit Enabled\n'.format(datetime.datetime.now()))
        print 'Indefinite Time Limit: press ctrl-c to quit at any time'
    else:
        log.write('{:%Y-%m-%d %H:%M:%S} {} Minute Time Limit\n'.format(datetime.datetime.now(), timelimit))
        print '{} Minute Time Limit'.format(timelimit)

    # writes a file that can feed into a deterministic run
    dir_path = os.path.join(os.path.dirname(__file__), 'deterministic-runs/')
    # create directory if it doesn't exist
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    deterministic_filename = dir_path + str(global_starttime).replace(' ', '_') + '-run.txt'
    deterministic_file = open(deterministic_filename, 'w')

    # create thread for number of faults
    while numfaults > 0:
        threads.append(threading.Thread(target=node_fault.stateless, args=(deterministic_file, timelimit)))
        numfaults -= 1

    # start all threads
    for thread in threads:
        thread.start()

    # wait for all threads to end
    not_done = True
    while not_done:
        not_done = False
        for thread in threads:
            if thread.isAlive():
                not_done = True
        time.sleep(1)

    deterministic_file.close()


def signal_handler(signal, frame):
    print '\nExit signal received.\nPlease wait while your environment is restored.\n ' \
          'Must allow all fault threads to finish.\n This may take some time...'

    log.write('{:%Y-%m-%d %H:%M:%S} Signal handler\n'.format(datetime.datetime.now()))

    stopper.set()

    for thread in threads:
        thread.join()

    subprocess.call('ansible-playbook playbooks/restart-nodes.yml', shell=True)

    # clean up tmp files
    for f in os.listdir('playbooks/'):
        if re.search('tmp_.*', f):
            os.remove(os.path.join('playbooks/', f))

    log.write('{:%Y-%m-%d %H:%M:%S} Fault Injector Stopped\n'.format(datetime.datetime.now()))
    log.close()

    sys.exit(0)


if __name__ == '__main__':
    main()
