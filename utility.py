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

    # 接收窗口打下，16位
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

fileWriterEnd = False
#磁盘每1s进行一次写操作
FileWriteInterval = 1
LastByteRcvd = 0
LastByteRead = 0
RcvBuffer = 100

def fileWriter(filename,d,timeQueue):
    global fileWriterEnd,LastByteRead

    while not fileWriterEnd:
        try:
            q = timeQueue.get(timeout = FileWriteInterval)
        except queue.Empty:
            f = open(filename,"ab+") 
            while len(d)>0:
                packet = d.popleft()
                LastByteRead = packet["SEQ_NUM"]
                f.write(packet["DATA"])
                # print(LastByteRead)
                # print(packet["DATA"])
            f.close()
            print("fileWriter")

def fileReceiver(port,ser_recv_addr,filename):
    global fileWriterEnd,LastByteRead

    # 接收方接收和发送端口
    recv_sock = socket(AF_INET,SOCK_DGRAM)
    recv_sock.bind(('',port))
    print(ser_recv_addr)

    # 期望得到的序号
    expectedSeqValue = 1
    # 计时器用于计算速度
    start_time = time.time()
    # 传输文件大小
    total_length = 0
    
    # 控制写入文件速度
    d = deque()
    timeQueue = queue.Queue()
    fileThread = threading.Thread(target=fileWriter,args=(filename,d,timeQueue,))
    fileThread.start()
    # fileThread.join()


    while True:
        data,addr = recv_sock.recvfrom(1024)
        packet = bits2dict(data)
        print("receive packet with seq",packet["SEQ_NUM"])
        #随机丢包
        '''
        if random.random()>0.8:
            #print("Drop packet")
            continue
        '''
        if packet["FIN"] == b'1':#如果收到FIN包，则退出
            print("receive eof, client over.")
            # recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue,"ACK":b'1',"recvWindow":RcvBuffer - (LastByteRcvd-LastByteRead)}),ser_recv_addr)
            break
        elif packet["SEQ_NUM"] == expectedSeqValue:
            print("Receive packet with correct seq value:",expectedSeqValue)
            # 更新确认序号
            LastByteRcvd = packet["SEQ_NUM"]
            d.append(packet)
            print(packet["DATA"])
            
            total_length += len(packet["DATA"])
            print(RcvBuffer - (LastByteRcvd-LastByteRead))
            recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue,"ACK":b'1',"recvWindow":RcvBuffer - (LastByteRcvd-LastByteRead)}),ser_recv_addr)
            expectedSeqValue += 1
        else:#收到了不对的包，则返回expectedSeqValue-1，表示在这之前的都收到了
            print("Expect ",expectedSeqValue," while receive",packet["SEQ_NUM"]," send ACK ",expectedSeqValue-1,"to receiver ",ser_recv_addr)
            recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue-1,"ACK":b'1',"recvWindow":RcvBuffer - (LastByteRcvd-LastByteRead)}),ser_recv_addr)

    #s.sendto(generateBitFromDict({"FIN":b'1'}),('127.0.0.1',9999))#关闭服务器，调试用
    fileWriterEnd = True
    end_time = time.time()
    total_length/=1024
    total_length/=(end_time-start_time)
    print("Transfer speed",total_length,"KB/s")



# 报文数据字段最大长度
MSS = 1
# 发送方最大时延
senderTimeoutValue = 0.5
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

def TransferSender(port,receiveQueue,filename,cli_addr,rwnd):
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
    # 是否为流控制
    ClientBlock = False
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
            if sendNotAck >=N or sendNotAck >= cwnd:
                sendAvaliable = False
                # print("Up to limit ",nextseqnum - base,N)
                # print("最大缓存：",rwnd)
                # print("Client cache full.")
            elif sendNotAck >= rwnd:
                sendAvaliable = False
                ClientBlock = True
            else:
                # 每次报文中数据的字节长度
                data = f.read(MSS)
                # 文件读入完毕
                if data == b'':
                    print("File read end.")
                    sendAvaliable = False
                    sendContinue = False
                    break
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

                # if sendNotAck <= rwnd:
                #     ClientBlock = False
                # else:
                #     ClientBlock = True
                
                if ack >= base:
                    # 更新base
                    base = ack+1
                    GBNtimer = time.time()
                    # 更新已发未收到ACK的包的数量
                    sendNotAck = nextseqnum - base
                    # 脱离超时循环
                    receiveACK = True
                    # 一次RTT完成，未发生拥塞，根据状态增加cwnd
                    if base == nextseqnum:     
                        sendAvaliable =True
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
                else:
                    previousACK = ack
                    dupACKcount = 1
                
                # 没收到响应的ack，如冗余的ack，没有更新计时器
                currentTime = time.time()
                # 由阻塞控制引起的超时
                if currentTime - GBNtimer > senderTimeoutValue and not ClientBlock:
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
                elif currentTime - GBNtimer > senderTimeoutValue and ClientBlock:
                    # 重启计时器
                    GBNtimer = time.time()
                    # 发送空包等到接收方将更新后的rwnd返回
                    send_sock.sendto(dict2bits({}),cli_addr)
                    sendNotAck = nextseqnum - base 
                    # if sendNotAck < rwnd:
                    #     receiveACK = True
                    #     sendAvaliable = True
                    if sendNotAck <= rwnd:
                        ClientBlock = False
                    else:
                        ClientBlock = True

            # 接收端发送的包超时
            except queue.Empty: 
                if not ClientBlock:
                    baseRepeat = base
                    print("Time out and output current sequence number",base)
                    ForceTime += 1
                    if ForceTime > 3:
                        ForceTime = 0
                        baseRepeat -= 10
                        if baseRepeat<0:
                            baseRepeat = 0
                    GBNtimer = time.time()#更新计时器
                    for i in range(baseRepeat,nextseqnum):
                        packet = cache[i]
                        print("Check resend packet SEQ:",bits2dict(packet)["SEQ_NUM"])
                        send_sock.sendto(packet,cli_addr)
                    congestionState = 1
                    ssthresh = int(cwnd)/2
                    cwnd = 1
                else:    
                    print("Update flow control value.")
                    GBNtimer = time.time()
                    # 发送空包等到接收方将更新后的rwnd返回
                    send_sock.sendto(dict2bits({}),cli_addr)
                    sendNotAck = nextseqnum - base 
                    # if sendNotAck <= rwnd:
                    #     receiveACK = True
                    #     sendAvaliable = True
                    if sendNotAck <= rwnd:
                        ClientBlock = False
                        sendAvaliable = True
                    else:
                        ClientBlock = True
            
    #关闭接受端与客户端
    send_sock.sendto(dict2bits({"FIN":b'1'}),cli_addr)
    send_sock.close()
    f.close()
    print("sender closes")