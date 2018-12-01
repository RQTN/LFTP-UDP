from socket import *
from time import ctime
import sys
sys.path.append('../')
from utility import *
import json
import threading
import time
import queue
from collections import deque

SER_PORT = 10000
SER_IP = "127.0.0.1"
ADDR = (SER_IP,SER_PORT)
BUFSIZE = 1024
MSS = 1024
APP_PORT = 30000

FILENAME = "test.txt"
OPERATION = "download"
fileWriterEnd = False
#磁盘每1s进行一次写操作
FileWriteInterval = 1
LastByteRcvd = 0
LastByteRead = 0
RcvBuffer = 10

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
            recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue,"ACK":b'1',"recvWindow":RcvBuffer - (LastByteRcvd-LastByteRead)}),ser_recv_addr)
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

# 用户选项
jsonOptions = bytes(json.dumps({'filename':FILENAME,"operation":OPERATION}),encoding="utf-8")

dict = {}
dict["SEQ_NUM"] = 1
dict["OPTIONS"] = jsonOptions
dict["OPT_LEN"] = len(jsonOptions)
dict["recvWindow"] = RcvBuffer

send_sock = socket(AF_INET,SOCK_DGRAM)
send_sock.bind(('',APP_PORT))

size = send_sock.sendto(dict2bits(dict),ADDR) 
print("Send size: ",size)

data , address = send_sock.recvfrom(1024)
appPort = json.loads(data.decode('utf-8'))['appPort']
print(appPort)
send_sock.close()

if OPERATION == "download":
    receiver_thread = threading.Thread(target = fileReceiver,args = (APP_PORT,(SER_IP,appPort),FILENAME,))
    receiver_thread.start()
    receiver_thread.join()
