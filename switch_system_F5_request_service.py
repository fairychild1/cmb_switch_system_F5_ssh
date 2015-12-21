#!/usr/bin/python
# -*- coding:utf-8 -*-
'''
author:wangying
date:2015-10-15
description:替换掉并发切换NA负责的功能。原理是通过建立一个监听程序入口，不停监听对F5网络设备的服务请求，监听程序将服务请求传递
给服务端程序，服务端程序如果发现到F5设备的连接已经存在，那么直接使用已有的连接来处理请求，然后将结果反馈给监听程序；如果不存在，
那么新建一个连接，处理完请求后将结果反馈给监听程序，同时在内存里保持跟F5设备的连接，来实现下次连F5设备并执行命令的时候要快的目的。
监听程序对于发来的多个请求，是并发处理的，如对同一个F5设备的请求，是并发来处理，不需要等待，这样的处理方式比原来NA上使用的expect
脚本串行执行请求要快。
'''
import socket
import os
import paramiko
import time
import datetime
import threading
import sys
import re
import logging
import traceback
import commands
from Queue import Queue

##########################################服务请求接收线程说明##########################################
#定义服务请求接收线程，该类的实例作用是不停接收客户进程发送过来的请求，并将client端和服务端建立的进程间的连接添加到服务请求队列
#Queue_Service_Request中。
##########################################服务请求接收线程说明##########################################
class Producer_Receive_Service_Request(threading.Thread):
    def __init__(self,Queue_Service_Request):
        threading.Thread.__init__(self)
        self.Queue_Service_Request=Queue_Service_Request
    def run(self):
        try:
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            if os.path.exists("/tmp/test.sock"):
                os.unlink("/tmp/test.sock")
            server.bind("/tmp/test.sock")
            server.listen(0)
            while True:
                connection,address = server.accept()
                self.Queue_Service_Request.put(connection)
        except:
            print 'ssh connection failed!'

##########################################服务请求处理线程说明##########################################
#定义服务请求处理线程，该类的线程的作用是处理Queue_Service_Request队列中的请求，首先判断接收到的关键字是否是connect_F5#F5_IP#USERNAME#PASSWORD
# 这样的字符串，如果是那么就处理到设备的连接：具体方式为如果连接池里已经有跟设备的连接，那么就拿到这个连接，如果没有到这个设备的连接，
#就新建一个连接。如果从客户端接收的字符串是以command打头的命令，那么就执行命令。队列ssh_connection_F5_array里面，保存的是已有连接的
#F5设备的ip地址，队列ssh_connection_ssh_array里保存的是已有连接的句柄，该队列是连接池。
##########################################服务请求处理线程说明##########################################
class Customer_Deal_Service_Request(threading.Thread):
    def __init__(self,Queue_Service_Request,F5_Connection_structrue,logger):
        threading.Thread.__init__(self)
        self.Queue_Service_Request=Queue_Service_Request
        self.F5_Connection_structrue=F5_Connection_structrue
#        self.ssh_connection_F5_array=ssh_connection_F5_array
#        self.ssh_connection_ssh_array=ssh_connection_ssh_array
    def run(self):
        while True:
            connection=self.Queue_Service_Request.get()
            ######################处理跟某个client的连接######################
            while True:
                try:
                    str_socket_recv=connection.recv(1024)
                    if cmp(str_socket_recv,"")==0:
                        break
                    ###########逻辑判断，如果是连接字符串，那么就获取连接，否则就执行命令###############
                    if re.search(r'connect_F5Ω\d+\.\d+\.\d+\.\d+Ω.*Ω.*',str_socket_recv):
                        argument_connection=str_socket_recv.split('Ω')
                        F5_ip=argument_connection[1]
                        F5_username=argument_connection[2]
                        F5_password=argument_connection[3]
                        ###########如果到F5设备的连接在连接池里没有，那么就要新建连接###########
                        flag_temp,position_temp=Index_of_element_in_list(self.F5_Connection_structrue,F5_ip)
                        if flag_temp==False:
                            logger.info('the service would ceate the connection to '+F5_ip)
                            (ssh,status)=New_ssh2_Connection(F5_ip,F5_username,F5_password)
                            #######如果新建连接失败，那么就显示错误信息#######
                            if status==1:
                                logger.error("create the connection to "+F5_ip+" failed!")
                                connection.send("can't connect %s,check the username and password!"% F5_ip)
                            else:
                                idle_time=Get_time_now()
                                self.F5_Connection_structrue.append([F5_ip,ssh,0,idle_time])
                                self.F5_connection=F5_ip
                                result='connect '+F5_ip+' success!'
                                logger.info(result)
                        else:
                            result='connection '+F5_ip+' already exists'
                            logger.info(result)
                            self.F5_connection=F5_ip
                    ##################发过来的如果是命令，那么就执行##################
                    elif re.search(r'commandΩ',str_socket_recv):
                        argument_connection=str_socket_recv.split('Ω')
                        F5_command=argument_connection[1]
                        F5_command_timeout=argument_connection[2]
                        logger.info('the service is going to exec command as below in F5 device.')
                        logger.debug('the command is:'+F5_command)
                        logger.debug('the command timeout user set is:%s'%F5_command_timeout)
                        logger.info('the F5 connection is:'+self.F5_connection)
                        flag_temp,position_temp=Index_of_element_in_list(self.F5_Connection_structrue,self.F5_connection)
                        self.F5_Connection_structrue[position_temp][2]+=1
                        status,result=Exec_command_status_result(self.F5_Connection_structrue[position_temp][1],F5_command,int(F5_command_timeout))
#                        logger.info("the connection %s is now used by %d thread!"%(self.F5_connection,self.F5_Connection_structrue[position_temp][2]))
                        self.F5_Connection_structrue[position_temp][2]-=1
                        logger.info('the command result is:')
                        logger.info('\n'+result)
                        result='run_command_status_result isΩ%dΩ%s'%(status,result)
                    ##################发过来的不是连接字符串，也不是命令，就直接报错##################
                    else:
                        result='bad arguments format!'
                        logger.error(result)
                    connection.send("%s"% result)
                except:
                    traceback.print_exc(file=sys.stdout)

class Release_F5_Connection_When_Idle_Timeout(threading.Thread):
    def __init__(self,F5_Connection_structrue,logger,timeout):
        threading.Thread.__init__(self)
        self.timeout=timeout
    def run(self):
        while True:
            try:
                for position,F5_connection_data_temp in enumerate(F5_Connection_structrue):
                    F5_Connection=F5_connection_data_temp[0]
                    if F5_connection_data_temp[2]!=0:
                        F5_connection_data_temp[3]=Get_time_now()
                    else:
                        Now_time=Get_time_now()
                        if (Now_time-F5_connection_data_temp[3]).seconds>=self.timeout:
                            logger.info("the connection %s is now in idle,it will be release!"%F5_Connection)
                            self.Release_F5_Connection(F5_Connection_structrue,position)
                            logger.info("the connection %s is released successfully!"%F5_Connection)
                time.sleep(0.1)
            except:
                traceback.print_exc(file=sys.stdout)
############释放F5设备的连接############
    def Release_F5_Connection(self,F5_Connection_structrue,position):
        F5_Connection_structrue[position][1].close()
        del F5_Connection_structrue[position]
###########获取当前时间的函数###########
def Get_time_now():
    return datetime.datetime.now()
###########定义方法，判断某元素是否在一个list里面###########
def Whether_element_in_list(list,element):
    flag=0
    for i in list:
        if cmp(i[0],element)==0:
            flag=1
            break
    if flag==0:
        return False
    else:
        return True

def Index_of_element_in_list(list,element):
    flag=0
    position=0
    for index,item in enumerate(list):
        if cmp(item[0],element)==0:
            flag=1
            position=index
            break
    if flag==0:
        return False,0
    else:
        return True,position
###########新建F5设备的连接，如果连接建立成功，那么返回连接的句柄，和状态码0，如果不成功，那么返回error字符，和状态码1###########
def New_ssh2_Connection(F5_ip,username,passwd):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(F5_ip,22,username,passwd,timeout=60)
        return (ssh,0)
    except :
        print '%s\tconnection Error'%(F5_ip)
        return ('error',1)

##################在F5设备上执行命令##################
def Exec_command_status_result(ssh,command,timeout=10):
    try:
        ###status为执行命令后的状态，正常则为0，运行错误，则为非0###
        status=0
        stdin,stdout,stderr=ssh.exec_command(command,timeout=timeout)
        stdout_result=stdout.read()
        stderr_result=stderr.read()
        cmd_result=stdout_result+stderr_result
        if stderr_result:
            status=1
        ###############如果执行的命令有结果，那么返回这个结果，如果执行的命令没有结果，比如sleep之类的命令，
        ###############那么返回一个换行符
        if cmp(cmd_result,'')==0:
            return (status,'\n')
        else:
            return (status,cmd_result.strip())
    ##########如果执行时间超时，那么返回超时的提示符##########
    except socket.timeout:
        status=2
        return (status,'exec command timeout!')
    except SSHException:
        status=3
        return (status,'failed to execute the command!')


def logger(name,level=logging.DEBUG):
    logger=logging.getLogger(name)
    logger.setLevel(level)
    # 创建一个handler，用于写入日志文件,日志保存到/var/switch_system_F5下面，以天为单位，每天的日志放在一个文件里，每个月的日
    # 志放在一个文件夹里
    path='/var/switch_system_F5/'+time.strftime('%Y_%m')+'/'
    if not os.path.exists(path):
        os.makedirs(path)
    file_name='switch_system_'+time.strftime('%Y%m%d')+'.log'
    file_handle=logging.FileHandler(path+file_name)
    file_handle.setLevel(level)
    # 再创建一个handler，用于输出到控制台
    ctr_handle=logging.StreamHandler()
    ctr_handle.setLevel(level)
    # 定义handler的输出格式
    formatter = logging.Formatter('[%(levelname)s]:%(asctime)s- %(message)s')
    file_handle.setFormatter(formatter)
    ctr_handle.setFormatter(formatter)
    # 给logger添加handler
    logger.addHandler(file_handle)
    logger.addHandler(ctr_handle)
    return logger

def Consist_Service_Confirm():
    array_argv0=os.path.realpath(sys.argv[0]).split('/')
    self_script_name=array_argv0[len(array_argv0)-1]
    command='ps -ef|grep '+self_script_name+'|grep -v grep|wc -l'
    result=commands.getoutput(command)
    if int(result)>=2:
        print "the switch system service is already running!"
        exit(0)

if __name__ == '__main__':
    MAX_THREAD=10
    TIME_OUT=60   #F5设备的连接超时时间
    Consist_Service_Confirm()
    Queue_Service_Request=Queue()
    F5_Connection_structrue=[]
    ###F5_Connection_structrue是一个数组，它保存的是已经建立的跟F5设备的连接，它的每一个元素都是一个小数组，小数组的构成如下：
    ###【F5_ip,ssh_connection,Thread_number,idle_time】
    logger=logger('cmb_logger')
    a=Producer_Receive_Service_Request(Queue_Service_Request)
    b=Release_F5_Connection_When_Idle_Timeout(F5_Connection_structrue,logger,TIME_OUT)
    thread_array=[]
    for i in range(MAX_THREAD):
        thread_temp=Customer_Deal_Service_Request(Queue_Service_Request,F5_Connection_structrue,logger)
        thread_array.append(thread_temp)
    a.start()
    b.start()
    for i in range(MAX_THREAD):
        thread_array[i].start()
    a.join()
    b.join()
    for i in range(MAX_THREAD):
        thread_array[i].join()


