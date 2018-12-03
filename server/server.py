#coding:utf-8
from socket import *
from time import ctime
import sys
sys.path.append('../')
from utility import *
import json
import queue
import threading
import time

# 默认选项
# 连接端口
SER_PORT = 10000
SER_IP = "127.0.0.1"
SER_ADDR = (SER_IP,SER_PORT)
BUFSIZE = 1024 
# 传输端口
APP_PORT = 20000
OPERATION = "lget"
FILENAME = "test.mp4"

# 服务端监听请求连接的套接字
recv_sock = socket(AF_INET, SOCK_DGRAM)
recv_sock.bind(SER_ADDR)
print("Server start to work on address",SER_ADDR)
serverListend = True

# 支持并发请求
while serverListend:
    # 接收客户端的请求
    data , address = recv_sock.recvfrom(BUFSIZE)
    packet = bits2dict(data)
    print("客户端地址: ",address)
    # print("SYN ",packet["SYN"])

    # 判断第一次是否为建立连接
    if packet["SYN"] == b'1':
        # 得到客户端的具体请求选项，如文件名和操作类型
        jsonOptions = packet["OPTIONS"].decode("utf-8")
        jsonOptions = json.loads(jsonOptions)
        # 请求文件名
        FILENAME = jsonOptions["filename"]
        # 请求操作
        OPERATION = jsonOptions["operation"]
        # 客户端缓存
        RecvBuffer = packet["recvWindow"]
        # print("CLIENT REQUEST:filename,operation,RecvBuffer:\n",FILENAME,OPERATION,RecvBuffer)
        print("客户端选项为: 文件名 操作 缓存大小 \n",FILENAME,OPERATION,RecvBuffer)

        # 返回服务端进行数据传送新的可用端口，不同于第一次连接的端口，每次请求返回的端口号确保不同
        replyPort = bytes(json.dumps({"replyPort":APP_PORT}),encoding = 'utf-8')
        recv_sock.sendto(replyPort,address)

        # 子线程处理下载请求
        if OPERATION == "lget":
            # 文件发送方共享的ack队列
            transferQueue = queue.Queue()
            # 发送方接收ACK的线程
            recv_thread = threading.Thread(target = TransferReceiver,args = (APP_PORT,transferQueue,))
            # 发送方发送文件内容的线程
            send_thread = threading.Thread(target = TransferSender,args = (APP_PORT+1,transferQueue,FILENAME,(address[0],address[1]),RecvBuffer,))
            
            # 更新新的端口处理其他请求
            APP_PORT += 2
            recv_thread.start()
            send_thread.start()

        # 子线程处理上传请求
        elif OPERATION == "lsend":
            # 文件接收方的线程
            receiver_thread = threading.Thread(target = fileReceiver,args = (APP_PORT,(address[0],address[1]),FILENAME,RecvBuffer,))
            # 更新新的端口处理其他请求
            APP_PORT += 1
            receiver_thread.start()
            
recv_sock.close()