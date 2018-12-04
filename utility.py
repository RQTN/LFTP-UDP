#coding:utf-8
from socket import *
from time import ctime
import sys
import json
import threading
import time
import queue
from collections import deque

def int2bits(value,length):
    return bytes(bin(value)[2:].zfill(length),encoding='utf-8')

# 字典转二进制码
def dict2bits(dict):
    bitstream = b''
    # 4位首部长度
    if "LENGTH" in dict:
        bitstream += int2bits(dict["LENGTH"],4)
    else:
        bitstream += int2bits(0,4)

    # 字节流序号，32位
    if "SEQ_NUM" in dict:
        bitstream += int2bits(dict["SEQ_NUM"],32)
    else:
        bitstream += int2bits(0,32)

    # 确认序号，32位
    if "ACK_NUM" in dict:
        bitstream += int2bits(dict["ACK_NUM"],32)
    else:
        bitstream += int2bits(0,32)

    # 接收窗口大小，16位
    if "recvWindow" in dict:
        bitstream += int2bits(dict["recvWindow"],16)
    else:
        bitstream += int2bits(0,16)

    # 确认位
    if "ACK" in dict:
        bitstream += dict["ACK"]
    else:
        bitstream += b'0'

    # 同步位
    if "SYN" in dict:
        bitstream += dict["SYN"]
    else:
        bitstream += b'0'
        
    # 终止位
    if "FIN" in dict:
        bitstream += dict["FIN"]
    else:
        bitstream += b'0'

    # 88位
    bitstream += b'0'
     
    # 选项长度，8位
    if "OPT_LEN" in dict:
        bitstream += int2bits(dict["OPT_LEN"],8)
    else:
        bitstream += int2bits(0,8)

    if "OPTIONS" in dict:
        bitstream += dict["OPTIONS"]
    
    if "DATA" in dict:
        bitstream += dict["DATA"]

    return bitstream

# 二进制转字典，解析报文
def bits2dict(bitstream):
    dict = {}
    dict["LENGTH"] = int(bitstream[0:4],2)
    dict["SEQ_NUM"] = int(bitstream[4:36],2)
    dict["ACK_NUM"] = int(bitstream[36:68],2)
    dict["recvWindow"] = int(bitstream[68:84],2)
    dict["ACK"] = bytes(str(bitstream[84] - 48),encoding='utf-8')
    dict["SYN"] = bytes(str(bitstream[85] - 48),encoding='utf-8')
    dict["FIN"] = bytes(str(bitstream[86] - 48),encoding='utf-8')
    dict["OPT_LEN"] = int(bitstream[88:96],2)
    dict["OPTIONS"] = bitstream[96:96+dict["OPT_LEN"]]
    dict["DATA"] = bitstream[96+dict["OPT_LEN"]:]
    return dict


# 硬盘每0.5s进行一次写操作
FileWriteInterval = 0.5
# 写文件线程：d为接收数据缓存，timeQueue为空的时间队列
def fileWriter(filename,d,timeQueue,shaVar):

    f = open(filename,"ab+") 
    # 文件未写完
    while not shaVar["fileWriterEnd"]:
        try:
            # 每隔FileWriteInterval获取空的队列
            q = timeQueue.get(timeout = FileWriteInterval)
        except queue.Empty:# 抛出异常
            while len(d)>0:
                packet = d.popleft()
                # 更新变量
                shaVar["LastByteRead"] = packet["SEQ_NUM"]
                # 写入数据
                f.write(packet["DATA"])
                # print(LastByteRead)
                # print(packet["DATA"])
            # print("等待写入文件")

    f.close()
    print("写入文件完成")

# 文件接收端的线程
# port：接收端口
# ser_recv_addr：返回ack的地址
# filename：文件名
# RcvBuffer：接收缓存大小
def fileReceiver(port,ser_recv_addr,filename,RcvBuffer):

    # 初始化
    shaVar = {}
    shaVar["fileWriterEnd"] = False
    shaVar["LastByteRead"] = 0
    LastByteRcvd = 0

    # 绑定UDP端口
    recv_sock = socket(AF_INET,SOCK_DGRAM)
    recv_sock.bind(('',port))
    print("文件接收端收到的发送端地址",ser_recv_addr)

    # 期望得到的序号
    expectedSeqValue = 1
    # 计时器用于计算速度
    start_time = time.time()
    # 传输文件大小
    total_length = 0
    
    # 控制写入文件速度
    # 写文件线程
    # d为共享的接收数据缓存队列
    d = deque()
    timeQueue = queue.Queue()
    fileThread = threading.Thread(target=fileWriter,args=(filename,d,timeQueue,shaVar,))
    fileThread.start()
    # fileThread.join()


    while True:
        data,addr = recv_sock.recvfrom(1024)
        packet = bits2dict(data)
        # 显示收到的seq_num
        print("收到的字节序号",packet["SEQ_NUM"]*500)
        #随机丢包
        '''
        if random.random()>0.8:
            #print("Drop packet")
            continue
        '''
        # 如果收到FIN包，则终止
        if packet["FIN"] == b'1':
            print("收到 FIN, 文件接收端关闭.")
            break

        # 按顺序得到
        elif packet["SEQ_NUM"] == expectedSeqValue:
            # print("Receive packet with correct seq value:",expectedSeqValue*500)
            print("收到正确的数据包，字节序号为",expectedSeqValue*500)
            # 更新确认序号
            LastByteRcvd = packet["SEQ_NUM"]
            # 加入缓存用于文件写入
            d.append(packet)
            # print(packet["DATA"])
            # 更新总长度
            total_length += len(packet["DATA"])
            # print(RcvBuffer - (LastByteRcvd-shaVar["LastByteRead"]))
            # 返回ack和接收缓存大小
            recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue,"ACK":b'1',"recvWindow":RcvBuffer - (LastByteRcvd-shaVar["LastByteRead"])}),ser_recv_addr)
            # 期望值+1
            expectedSeqValue += 1

        #收到了不对的包，则返回expectedSeqValue-1，表示在这之前的都收到了
        else:
            print("期待得到的字节序号 ",expectedSeqValue*500," 实际收到: ",packet["SEQ_NUM"]*500," 发送ack序号为: ",(expectedSeqValue-1)*500,"到发送端: ",ser_recv_addr)
            recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue-1,"ACK":b'1',"recvWindow":RcvBuffer - (LastByteRcvd-shaVar["LastByteRead"])}),ser_recv_addr)

    # 跳出循环
    shaVar["fileWriterEnd"]  = True
    end_time = time.time()
    total_length/=1024
    total_length/=(end_time-start_time)
    print("文件传输速度为: ",total_length,"KB/s")

# 发送方接收ack线程
# port：接收端口
# receiveQueue：共享ack队列
def TransferReceiver(port,receiveQueue):

    receiverSocket = socket(AF_INET,SOCK_DGRAM)
    receiverSocket.bind(('',port))

    while True:
        data,addr = receiverSocket.recvfrom(1024)
        # print(addr)
        packet = bits2dict(data)
        # 加入ack队列
        receiveQueue.put(packet)
        print("发送端收到ack序号为: ",packet["ACK_NUM"]*500)
        # print("receiver window size:",packet["recvWindow"])

    receiverSocket.close()

# 发送端发送数据线程
# port：发送端口
# receiveQueue：共享ack队列
# filename：文件名
# cli_addr：接收方地址
# rwnd：接收方缓存
def TransferSender(port,receiveQueue,filename,cli_addr,rwnd):
    send_sock = socket(AF_INET,SOCK_DGRAM)
    send_sock.bind(('',port))
    # print(cli_addr)

    ### 初始化
    # 发送报文数据字段最大字节长度
    MSS = 500
    # 发送方最大等待时延
    senderTimeoutValue = 0.5
    # 拥塞窗口大小
    cwnd = 1
    # 慢启动阈值
    ssthresh = 500
    # 重复ACK计数
    dupACKcount = 0
    # 最早没发送的
    nextseqnum = 1
    # 最早发送没收到的
    base = 1
    # 发送缓存
    cache = {}
    # 已发没收到ACK的包
    sendNotAck = 0
    # 计时器
    GBNtimer = 0
    # 是否发完
    sendContinue = True
    # 是否继续发送
    sendAvaliable = True
    # 是否为流控制
    ClientBlock = False
    # 1为指数增长；2为线性增长
    congestionState = 1

    f = open(filename,"rb")
    while sendContinue:
        # 可以发送数据
        while sendAvaliable:
            # 更新已发没收到ACK的包
            sendNotAck = nextseqnum - base
            # 每一轮开始启动计时器
            if base == nextseqnum:
                GBNtimer = time.time()
            # 如果大于min（rwnd,cwnd）窗口长度，cache则满   
            if sendNotAck >= cwnd:
                sendAvaliable = False
                print("已发没收到ACK的包 ",nextseqnum - base)
                print("当前cwnd大小：",cwnd)
            elif sendNotAck >= rwnd:
                sendAvaliable = False
                ClientBlock = True
                print("已发没收到ACK的包 ",nextseqnum - base)
                print("当前rwnd大小：",rwnd)
            else:
                # 每次读取报文中数据的字节长度
                data = f.read(MSS)
                # 文件读入完毕
                if data == b'':
                    print("文件已经读到末尾，结束.")
                    sendAvaliable = False
                    sendContinue = False
                    break
                # 发送缓存(base,base+N),用于重传 
                cache[nextseqnum] = dict2bits({"SEQ_NUM":nextseqnum,"DATA":data})
                send_sock.sendto(cache[nextseqnum],cli_addr)
                print("send packet:", nextseqnum)
                nextseqnum += 1
       

        # 等待接收ACK
        receiveACK = False
        # 前一个ACK
        previousACK = 0 
        while not receiveACK:
            try:
                # ack队列，最多等待senderTimeoutValue
                receiveData = receiveQueue.get(timeout = senderTimeoutValue)
                # ack序号
                ack = receiveData["ACK_NUM"]
                # 接收窗口大小，用于流量控制
                rwnd = receiveData["recvWindow"]
                # print(sendNotAck,rwnd)
                # if sendNotAck <= rwnd:
                #     ClientBlock = False
                # else:
                #     ClientBlock = True
                
                # 按顺序收到ACK
                if ack == base:
                    # 更新base
                    base = ack+1
                    # 更新计时器
                    GBNtimer = time.time()
                    # 更新已发未收到ACK的包的数量
                    sendNotAck = nextseqnum - base
                    # 记录上一个ack
                    previousACK = ack
                    dupACKcount = 1
                    # 一次RTT完成，未发生拥塞，根据状态增加cwnd
                    if base == nextseqnum:      
                        # 所有上一轮ack确认收到
                        receiveACK = True
                        # 继续下一轮发送
                        sendAvaliable =True
                        if not ClientBlock:
                            # 乘性增长
                            if congestionState == 1:
                                cwnd *= 2
                            else:
                                cwnd += 1
                            # 到达阈值线性增长
                            if cwnd >= ssthresh and congestionState == 1:
                                cwnd == ssthresh
                                congestionState = 2
                        ClientBlock = False
                        break
                        # 开始下一轮发送
                        
                # 收到重复ACK
                elif ack == previousACK:
                    dupACKcount += 1
                    # 进入快速恢复状态
                    if dupACKcount >= 3:
                        ssthresh = int(cwnd/2)
                        cwnd = ssthresh + 3
                        dupACKcount = 0
                        congestionState = 2
                        print("收到3次冗余的ACK",previousACK*500," ,进行重传!")
                        # 进入重传
                        GBNtimer = time.time()
                        for i in range(base,nextseqnum):
                            packet = cache[i]
                            send_sock.sendto(cache[i],cli_addr)

                            print("重传的字节序号为: ",bits2dict(packet)["SEQ_NUM"]*500)
                    continue
                
        
            # 收不到ack，抛出异常
            except queue.Empty:                  
                currentTime = time.time()

                if currentTime - GBNtimer > senderTimeoutValue and base != nextseqnum:
                    # print("Time out and output current sequence number",base)
                    print("超时,当前base为: ",base)

                    # 重启计时器
                    GBNtimer = time.time()
                    # 重传base到nextseqnum
                    for i in range(base,nextseqnum):
                        packet = cache[i]
                        send_sock.sendto(cache[i],cli_addr)
                        # print("Resend packet SEQ:",bits2dict(packet)["SEQ_NUM"]*500)
                        print("重传的字节序号为: ",bits2dict(packet)["SEQ_NUM"]*500)

                    congestionState = 1
                    ssthresh = int(cwnd)/2
                    if ssthresh<=0:
                        ssthresh = 1
                    cwnd = 1
                    receiveACK = True
                    sendAvaliable = True
                else:
                    print("Update flow control value.")
                    GBNtimer = time.time()
                    # 发送空包等到接收方将更新后的rwnd返回
                    send_sock.sendto(dict2bits({}),cli_addr)
                    print("send packet:", 0)
                    sendNotAck = nextseqnum - base 
                    if sendNotAck <= rwnd:
                        sendAvaliable = True
                        receiveACK = True
            
    #关闭接受端与客户端
    send_sock.sendto(dict2bits({"FIN":b'1'}),cli_addr)
    send_sock.close()
    f.close()
    # print("file sender closes")
    print("文件发送端关闭")
