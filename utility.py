import json


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
    dict["FIN"] = bytes(str(bitstream[85] - 48),encoding='utf-8')
    dict["SYN"] = bytes(str(bitstream[86] - 48),encoding='utf-8')
    dict["OPT_LEN"] = int(bitstream[88:96],2)
    dict["OPTIONS"] = bitstream[96:96+dict["OPT_LEN"]]
    dict["DATA"] = bitstream[96+dict["OPT_LEN"]:]
    return dict

    