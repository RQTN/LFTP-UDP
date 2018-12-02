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
SER_ADDR = (SER_IP,SER_PORT)
FILENAME = "test.mp4"
OPERATION = "lget"
RecvBuffer = 10
CLI_PORT = 30000
BUFSIZE = 1024 

if __name__ == '__main__':
    if len(sys.argv)>=4:
        OPERATION = sys.argv[1]
        SER_ADDR = sys.argv[2]
        FILENAME = sys.argv[3]
    else:
        print('''usage: LFTP
                      OPERATION [lsend | lget] 
                      SER_ADDR [(server_ip_addr,server_port)]
                      FILENAME ''')
        # sys.exit(0)

        
    # 用户选项
    jsonOptions = bytes(json.dumps({'filename':FILENAME,"operation":OPERATION}),encoding="utf-8")

    # 建立连接的报文首部信息
    dict = {}
    dict["SYN"] = b'1'
    dict["OPTIONS"] = jsonOptions
    dict["OPT_LEN"] = len(jsonOptions)
    dict["recvWindow"] = RecvBuffer

    # UDP套接字
    send_sock = socket(AF_INET,SOCK_DGRAM)
    send_sock.bind(('',CLI_PORT))

    size = send_sock.sendto(dict2bits(dict),SER_ADDR) 
    # print("Send size: ",size)

    # 等待服务端返回可用端口
    data , address = send_sock.recvfrom(BUFSIZE)
    replyPort = json.loads(data.decode('utf-8'))['replyPort']
    print("The server reply the port avalible at :",replyPort)
    send_sock.close()

    if OPERATION == "lget":
        receiver_thread = threading.Thread(target = fileReceiver,args = (CLI_PORT,(SER_IP,replyPort),FILENAME,))
        CLI_PORT += 2
        receiver_thread.start()
        receiver_thread.join()
    elif OPERATION == "lsend":
        # 发送方共享的队列
        transferQueue = queue.Queue()
        # 发送方接收ACK的线程
        # 参数：发送方接收端口
        recv_thread = threading.Thread(target = TransferReceiver,args = (CLI_PORT,transferQueue,))
        # 发送方发送文件内容的线程
        # 参数：发送方发送端口，接收方接收端口
        send_thread = threading.Thread(target = TransferSender,args = (CLI_PORT+1,transferQueue,FILENAME,(address[0],address[1]),))

        CLI_PORT += 2
        recv_thread.start()
        send_thread.start()
        recv_thread.join()
        recv_thread.join()