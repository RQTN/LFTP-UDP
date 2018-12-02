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
FILENAME = "test.txt"
RecvBuffer = 100

# 服务端监听连接的套接字
recv_sock = socket(AF_INET, SOCK_DGRAM)
recv_sock.bind(SER_ADDR)
print("Server start to work on address",SER_ADDR)
serverListend = True

# 支持并发请求
while serverListend:
    # 接收客户端的请求
    data , address = recv_sock.recvfrom(BUFSIZE)
    packet = bits2dict(data)
    print("CLIENT address",address)
    print("SYN ",packet["SYN"])

    if packet["SYN"] == b'1':
        # serverConnected = True

        # 得到客户端的具体请求内容
        jsonOptions = packet["OPTIONS"].decode("utf-8")
        jsonOptions = json.loads(jsonOptions)
        # 请求文件名
        FILENAME = jsonOptions["filename"]
        # 请求操作
        OPERATION = jsonOptions["operation"]
        RecvBuffer = packet["recvWindow"]
        print("CLIENT REQUEST:FILENAME,OPERATION,RecvBuffer:\n",FILENAME,OPERATION,RecvBuffer)

        # 返回新的可用端口，对于下载请求，即为服务端作为发送方接收的端口，对于上传，即为服务端作为接收方接收和发送的端口
        replyPort = bytes(json.dumps({"replyPort":APP_PORT}),encoding = 'utf-8')
        recv_sock.sendto(replyPort,address)

        # 子线程处理下载请求
        if OPERATION == "lget":
            # 发送方共享的队列
            transferQueue = queue.Queue()
            # 发送方接收ACK的线程
            # 参数：发送方接收端口
            recv_thread = threading.Thread(target = TransferReceiver,args = (APP_PORT,transferQueue,))
            # 发送方发送文件内容的线程
            # 参数：发送方发送端口，接收方接收端口
            send_thread = threading.Thread(target = TransferSender,args = (APP_PORT+1,transferQueue,FILENAME,(address[0],address[1]),RecvBuffer,))

            APP_PORT += 2
            recv_thread.start()
            send_thread.start()
            # recv_thread.join()
            # recv_thread.join()
        elif OPERATION == "upload":
            receiver_thread = threading.Thread(target = fileReceiver,args = (APP_PORT,(address[0],address[1]),FILENAME,))
            APP_PORT += 1
            receiver_thread.start()
            # receiver_thread.join()

recv_sock.close()