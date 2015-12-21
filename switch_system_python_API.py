#!/usr/bin/python
# -*- coding:utf-8 -*-
import socket
import os
import sys

#############连设备的API#############
class ssh_cmb:
    def __init__(self,F5,username,password):
        self.F5=F5
        self.username=username
        self.password=password
        self.client=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client.connect("/tmp/test.sock")
        self.client.send('connect_F5Ω'+F5+'Ω'+username+'Ω'+password)
        str_connect_recv=self.client.recv(1024)
        print str_connect_recv
#############执行命令的API函数exec_command说明#############
#执行命令的API函数exec_command,这个函数有两个参数：要执行的命令command和超时时间timeout，如果用户不指定超时
#时间，那么超时时间默认是10秒
#exec_command的返回值有两个，执行状态和执行结果。执行结果就是命令的结果。执行状态status是一个数字，如果正常执行，那么status为0，
#如果执行命令有错误，那么status为1，如果执行时间超时，那么status为2，如果有网络中断、服务器宕了或者CPU被占满等其他异常，
#那么status为3
#############执行命令的API函数exec_command说明#############
    def exec_command(self,command,timeout=10):
        self.client.send('commandΩ%sΩ%d'%(command,timeout))
        status_and_result=self.client.recv(1024)
        array_temp=status_and_result.split('Ω')
        return int(array_temp[1]),array_temp[2]
#############连设备的API#############

if __name__ == '__main__':
    F5_ip="192.168.132.128"
    username="root"
    password="nicemeeting1"
    whole_commands=""
    for i in sys.argv[1:]:
        whole_commands=whole_commands+' '+i
    array_commands=whole_commands.split('#')
#    Mode=sys.argv[3]
#    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
#    client.connect("/tmp/test.sock")
#    client.send(F5_ip+'#'+Device_ip+'#'+Mode)
#    print client.recv(1024)
#    client.close()
    ssh=ssh_cmb(F5_ip,username,password)
    (status,result)=ssh.exec_command(array_commands[0],20)
    print 'the status is %d,the result is:%s'%(status,result)





