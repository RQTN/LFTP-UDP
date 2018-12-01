from socket import *
from time import ctime
import sys
sys.path.append('../')
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

# 报文数据字段最大长度
MSS = 1
# 发送方最大时延
senderTimeoutValue = 0.001
# 接收窗口大小
rwnd = 0
# 拥塞窗口大小
cwnd = MSS
# 满启动阈值
ssthresh = 10
# 重复ACK计数
dupACKcount = 0

def TransferReceiver(port,receiveQueue):
    global rwnd
    receiverSocket = socket(AF_INET,SOCK_DGRAM)
    receiverSocket.bind(('',port))
    while True:
        data,addr = receiverSocket.recvfrom(1024)

        packet = bits2dict(data)
        receiveQueue.put(packet)
        print("receiver receive ack:",packet["ACK_NUM"])
        # print("receiver window size:",packet["recvWindow"])

    receiverSocket.close()
    print("receiver close")

def TransferSender(port,receiveQueue,filename,cli_addr):
    global rwnd
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
    
    # 1为指数增长；2为线性增长
    congestionState = 1
    # 是否是拥塞避免
    # congestionCtrl = False
    global dupACKcount,cwnd,ssthresh

    f = open(filename,"rb")
    while sendContinue:
        # 可以发送数据
        while sendAvaliable:
            
            # 已发没收到ACK的包
            sendNotAck = nextseqnum - base
            # 启动计时器
            if base == nextseqnum:
                GBNtimer = time.time()
            print("CWND",cwnd)
            # 如果大于窗口长度，cache则满   
            if sendNotAck >=N or sendNotAck >= rwnd or sendNotAck >= cwnd:
                sendAvaliable = False
                # print("Up to limit ",nextseqnum - base,N)
                # print("最大缓存：",rwnd)
                # print("Client cache full.")
            else:
                # 每次报文中数据的字节长度
                data = f.read(MSS)
                # 文件读入完毕
                if data == b'':
                    print("File read end.")
                    sendAvaliable = False
                    sendContinue = False
                # 发送缓存(base,base+N),用于重传 
                cache[nextseqnum] = dict2bits({"SEQ_NUM":nextseqnum,"DATA":data})
                send_sock.sendto(cache[nextseqnum],cli_addr)
                nextseqnum += 1
       

        # 等待接收ACK
        receiveACK = False
        # 前一个ACK
        previousACK = 0 
        ForceTime = 0
        while not receiveACK:
            try:
                # 发送端接收端口收到的队列
                receiveData = receiveQueue.get(timeout = senderTimeoutValue)
                # ack序号
                ack = receiveData["ACK_NUM"]
                # 接收窗口大小，用于流量控制
                rwnd = receiveData["recvWindow"]
                # print(nextseqnum,base,rwnd)

                if ack >= base:
                    # 更新base
                    base = ack+1
                    previousACK = ack
                    dupACKcount = 1
                    # 更新已发未收到ACK的包的数量
                    # sendNotAck = nextseqnum - base
                    
                    # 一次RTT完成，未发生拥塞，根据状态增加cwnd
                    if base == nextseqnum:     
                        sendAvaliable =True
                        # 脱离超时循环
                        receiveACK = True
                        # 乘性增长
                        if congestionState == 1:
                            cwnd *= 2
                        else:
                            cwnd += MSS
                        # 到达阈值线性增长
                        if cwnd >= ssthresh and congestionState == 1:
                            cwnd == ssthresh
                            congestionState = 2
                        break
                # 收到重复ACK
                elif ack == previousACK:
                    dupACKcount += 1
                    # 进入快速恢复状态
                    if dupACKcount >= 3:
                        ssthresh = int(cwnd/2)
                        cwnd = ssthresh + 3*MSS
                        dupACKcount = 0
                        congestionState = 2
                        print("Three times duplicated ACK",previousACK," ,resend now!")
                        # 进入重传
                        raise queue.Empty
                    continue
                
                # 没收到响应的ack，如冗余的ack，没有更新计时器
                currentTime = time.time()
                # 由阻塞控制引起的超时
                if currentTime - GBNtimer > senderTimeoutValue:
                    print("Time out and output current sequence number",base)
                    # 重启计时器
                    GBNtimer = time.time()
                    baseRepeat = base
                    ForceTime += 1
                    if ForceTime > 3:
                        ForceTime = 0
                        baseRepeat -= 10
                        if baseRepeat<0:
                            baseRepeat = 0
                    # 重传
                    for i in range(baseRepeat,nextseqnum):
                        packet = cache[i]
                        send_sock.sendto(cache[i],cli_addr)
                        print("Check resend packet SEQ:",bits2dict(packet)["SEQ_NUM"])
                    congestionState = 1
                    ssthresh = int(cwnd)/2
                    if ssthresh<=0:
                        ssthresh = 1
                    cwnd = 1
                # 由超过接收窗口大小引起的超时
                elif currentTime - GBNtimer > senderTimeoutValue:
                    # 重启计时器
                    GBNtimer = time.time()
                    # 发送空包等到接收方将更新后的rwnd返回
                    send_sock.sendto(dict2bits({}),cli_addr)
                    sendNotAck = nextseqnum - base - 1
                    if sendNotAck < rwnd:
                        receiveACK = True
                        sendAvaliable = True

            # 接收端发送的包超时
            except queue.Empty: 
                # if congestionCtrl:
                #     print("Time out and output current sequence number",base)
                #     # 重启计时器
                #     GBNtimer = time.time()
                #     baseRepeat = base
                #     ForceTime += 1
                #     if ForceTime > 3:
                #         ForceTime = 0
                #         baseRepeat -= 10
                #         if baseRepeat<0:
                #             baseRepeat = 0
                #     # 重传
                #     for i in range(baseRepeat,nextseqnum):
                #         packet = cache[i]
                #         send_sock.sendto(cache[i],cli_addr)
                #         print("Check resend packet SEQ:",bits2dict(packet)["SEQ_NUM"])
                #     congestionState = 1
                #     ssthresh = int(cwnd)/2
                #     if ssthresh<=0:
                #         ssthresh = 1
                #     cwnd = 1
                # else:    
                    print("Update flow control value.")
                    GBNtimer = time.time()
                    # 发送空包等到接收方将更新后的rwnd返回
                    send_sock.sendto(dict2bits({}),cli_addr)
                    sendNotAck = nextseqnum - base - 1
                    if sendNotAck < rwnd:
                        receiveACK = True
                        sendAvaliable = True
                        congestionCtrl = True
            
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
rwnd = packet["recvWindow"]
print(filename,operation,rwnd)
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