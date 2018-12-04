#coding:utf-8
from socket import *
from time import ctime
import sys
sys.path.append('../')
from utility import *
import json
import threading

# 默认选项
SER_PORT = 10000
SER_IP = "127.0.0.1"
FILENAME = "test.mp4"
OPERATION = "lget"
RecvBuffer = 1000
CLI_PORT = 30000
BUFSIZE = 1024 

if __name__ == '__main__':
    # 根据命令行参数进行初始化
    if len(sys.argv)>=4:
        OPERATION = sys.argv[1]
        SER_IP = sys.argv[2]
        FILENAME = sys.argv[3]
    else:
        print("默认参数为 "+OPERATION+" "+SER_IP+" "+FILENAME)
        print('''usage: LFTP
                      OPERATION [lsend | lget] 
                      SER_ADDR 'server_ip_addr'
                      FILENAME 'test.mp4' ''')
        # sys.exit(0)

    SER_ADDR = (SER_IP,SER_PORT)

    # 用户选项
    jsonOptions = bytes(json.dumps({'filename':FILENAME,"operation":OPERATION}),encoding="utf-8")

    # 建立连接的报文首部信息
    dict = {}
    dict["SYN"] = b'1'
    dict["OPTIONS"] = jsonOptions
    dict["OPT_LEN"] = len(jsonOptions)
    dict["recvWindow"] = RecvBuffer

    # 客户端UDP套接字
    send_sock = socket(AF_INET,SOCK_DGRAM)
    send_sock.bind(('',CLI_PORT))

    # 发送连接请求
    size = send_sock.sendto(dict2bits(dict),SER_ADDR) 
    print("发送大小为: ",size)
    print("服务器地址: ",SER_ADDR)

    # 等待服务端返回可用端口
    data , address = send_sock.recvfrom(BUFSIZE)
    replyPort = json.loads(data.decode('utf-8'))['replyPort']
    # print("The server reply the port avalible at :",replyPort)
    print("服务端返回的可用端口为: ",replyPort)
    send_sock.close()

    # 处理下载
    if OPERATION == "lget":
        receiver_thread = threading.Thread(target = fileReceiver,args = (CLI_PORT,(SER_IP,replyPort),FILENAME,RecvBuffer,))
        receiver_thread.start()
        # 阻塞执行
        receiver_thread.join()
    elif OPERATION == "lsend":
        # 发送方共享的ack队列
        transferQueue = queue.Queue()
        # 发送方接收ACK的线程
        recv_thread = threading.Thread(target = TransferReceiver,args = (CLI_PORT,transferQueue,))
        # 发送方发送文件内容的线程
        send_thread = threading.Thread(target = TransferSender,args = (CLI_PORT+1,transferQueue,FILENAME,(address[0],replyPort),RecvBuffer,))
        recv_thread.start()
        send_thread.start()
        recv_thread.join()
        recv_thread.join()