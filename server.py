from socket import *
from time import ctime
from utility import *
import json
import queue
import threading
import time

SER_PORT = 10000
SER_IP = "127.0.0.1"
ADDR = (SER_IP,SER_PORT)
BUFSIZE = 1024 
APP_PORT = 20000
OPERATION = "download"

senderTimeoutValue = 0.5

def TransferReceiver(port,receiveQueue):
    receiverSocket = socket(AF_INET,SOCK_DGRAM)
    receiverSocket.bind(('',port))
    while True:
        data,addr = receiverSocket.recvfrom(1024)

        packet = bits2dict(data)
        receiveQueue.put(packet)
        print("receiver receive ack:",packet["ACK_NUM"])

    receiverSocket.close()
    print("receiver close")

def TransferSender(port,receiveQueue,filename,cli_addr):

    send_sock = socket(AF_INET,SOCK_DGRAM)
    send_sock.bind(('',port))
    print(cli_addr)

    # 初始化
    # 最早没发送的
    nextseqnum = 1
    # 最早发送没收到的
    base = 1
    N = 10
    cache = {}
    sendNotAck = 0
    GBNtimer = 0
    sendContinue = True
    sendAvaliable = True
    f = open(filename,"rb")
    while sendContinue:
        while sendAvaliable:#如果可以读入数据

            # 每次报文中数据的字节长度
            data = f.read(1)
            # 文件读入完毕
            if data == b'':
                print("File read end.")
                sendAvaliable = False
                sendContinue = False
            # 启动计时器
            if base == nextseqnum:
                GBNtimer = time.time()
            # 发送缓存(base,base+N),用于重传 
            cache[nextseqnum] = dict2bits({"SEQ_NUM":nextseqnum,"DATA":data})
            send_sock.sendto(cache[nextseqnum],cli_addr)
            nextseqnum += 1
            # 已发没收到ACK的包
            sendNotAck = nextseqnum - base

            # 如果大于窗口长度，cache则满   
            if sendNotAck >=N:
                sendAvaliable = False
                # print("Up to limit ",nextseqnum - base,N)
            


        # 等待接收ACK
        receiveACK = False
        while not receiveACK:
            # 发送端接收端口收到的队列
            receiveData = receiveQueue.get(timeout = senderTimeoutValue)
            # ack序号
            ack = receiveData["ACK_NUM"]
            # 接收窗口大小，用于流量控制
            rwnd = receiveData["recvWindow"]

            if ack >= base:
                # 更新base
                base = ack+1
                # 更新已发未收到ACK的包的数量
                sendNotAck = nextseqnum - base
                # 脱离超时循环
                receiveACK = True
                # 继续发送
                sendAvaliable = True
                # 更新计时器
                GBNtimer = time.time()
            
            # 没收到响应的ack，如冗余的ack，没有更新计时器
            currentTime = time.time()
            # 判断超时
            if currentTime - GBNtimer > senderTimeoutValue
                print("Time out and output current sequence number",base)
                # 更新计时器
                GBNtimer = time.time()
                # 重传
                for i range(base,nextseqnum):
                    packet = cache[i]
                    send_sock.sendtp(packet,cli_addr)
                    print("Check resend packet SEQ:",packet["SEQ_NUM"])
            
    f.close()
    send_sock.close()

# 服务端套接字
recv_sock = socket(AF_INET, SOCK_DGRAM)
recv_sock.bind(ADDR)
print("Server start to work on port",SER_PORT)

# 接收客户端的请求
data , address = recv_sock.recvfrom(BUFSIZE)
packet = bits2dict(data)

# 得到客户端的具体请求内容
jsonOptions = packet["OPTIONS"].decode("utf-8")
jsonOptions = json.loads(jsonOptions)
# 请求文件名
filename = jsonOptions["filename"]
# 请求操作
operation = jsonOptions["operation"]
print(filename,operation)
# 返回新的可用端口，对于下载请求，即为服务端作为发送方接收的端口，对于上传，即为服务端作为接收方接收和发送的端口
replyPort = bytes(json.dumps({"appPort":APP_PORT}),encoding = 'utf-8')
recv_sock.sendto(replyPort,address)

# 子线程处理下载请求
if operation == "download":
    # 发送方共享的队列
    transferQueue = queue.Queue()
    # 发送方接收ACK的线程
    # 参数：发送方接收端口
    recv_thread = threading.Thread(target = TransferReceiver,args = (APP_PORT,transferQueue,))
    # 发送方发送文件内容的线程
    # 参数：发送方发送端口，接收方接收端口
    send_thread = threading.Thread(target = TransferSender,args = (APP_PORT+1,transferQueue,filename,(address[0],address[1]),))
    
    APP_PORT += 2
    recv_thread.start()
    send_thread.start()
    recv_thread.join()
    recv_thread.join()