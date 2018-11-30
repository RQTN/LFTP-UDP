from socket import *
from time import ctime
from utility import *
import json
import threading
import time

SER_PORT = 10000
SER_IP = "127.0.0.1"
ADDR = (SER_IP,SER_PORT)
BUFSIZE = 1024
MSS = 1024
APP_PORT = 30000

FILENAME = "test.txt"
OPERATION = "download"

def fileReceiver(port,ser_recv_addr,filename):

    recv_sock = socket(AF_INET,SOCK_DGRAM)
    recv_sock.bind(('',port))
    print(ser_recv_addr)

    expectedSeqValue = 1
    start_time = time.time()
    total_length = 0

    with open(filename,"ab+") as f:
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
                recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue,"ACK":b'1',"recvWindow":100}),ser_recv_addr)
                break
            elif packet["SEQ_NUM"] == expectedSeqValue:
                print("Receive packet with correct seq value:",expectedSeqValue)
                f.write(packet["DATA"])
                print(packet["DATA"])
                total_length += len(packet["DATA"])
                recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue,"ACK":b'1',"recvWindow":100}),ser_recv_addr)
                expectedSeqValue += 1
            else:#收到了不对的包，则返回expectedSeqValue-1，表示在这之前的都收到了
                print("Expect ",expectedSeqValue," while receive",packet["SEQ_NUM"]," send ACK ",expectedSeqValue-1,"to receiver ",ser_recv_addr)
                recv_sock.sendto(dict2bits({"ACK_NUM":expectedSeqValue-1,"ACK":b'1',"recvWindow":100}),ser_recv_addr)

    f.close()
    #s.sendto(generateBitFromDict({"FIN":b'1'}),('127.0.0.1',9999))#关闭服务器，调试用
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
