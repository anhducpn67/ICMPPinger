import os
import select
import struct
import sys
import time
from socket import *

ICMP_ECHO_REQUEST = 8
numberPacketSent = 4  # Number client pings to server
serverName = "google.com"


def checksum(str_):
    # In this function we make the checksum of our packet
    str_ = bytearray(str_)
    csum = 0
    countTo = (len(str_) // 2) * 2

    for count in range(0, countTo, 2):
        thisVal = str_[count + 1] * 256 + str_[count]
        csum = csum + thisVal
        csum = csum & 0xffffffff

    if countTo < len(str_):
        csum = csum + str_[-1]
        csum = csum & 0xffffffff

    csum = (csum >> 16) + (csum & 0xffff)
    csum = csum + (csum >> 16)
    answer = ~csum
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer


def receiveOnePing(mySocket, ID, timeOut, destAddr):
    timeLeft = timeOut
    while 1:
        startedSelect = time.time()
        whatReady = select.select([mySocket], [], [], timeLeft)
        howLongInSelect = (time.time() - startedSelect)
        if not whatReady[0]:  # Timeout
            return "Request timed out."

        timeReceived = time.time()
        recPacket, addr = mySocket.recvfrom(1024)

        # Fetch the ICMP header from the IP packet
        beginICMPHeaderByte = 20  # The ICMP header starts after bit 160 (byte 20) of the IP header
        endICMPHeaderByte = 28  # Length of ICMP header = (8 + 8 + 16 + 16 + 16) bits = 8 bytes
        # => End of ICMP header after byte = 20 + 8 = 28
        icmpHeader = recPacket[beginICMPHeaderByte:endICMPHeaderByte]
        ICMPType, ICMPCode, ICMPCheckSum, ICMP_ID, ICMPSequence = struct.unpack("bbHHh", icmpHeader)
        if ICMPType == 0 and ICMPCode == 0 and ICMP_ID == ID:
            bytesInDouble = struct.calcsize("d")  # Calc size of double number in bytes
            # Data starts from end of ICMP header byte
            timeSent = struct.unpack("d", recPacket[endICMPHeaderByte:endICMPHeaderByte + bytesInDouble])[0]
            return timeReceived - timeSent  # Return delay (RTT)

        timeLeft = timeLeft - howLongInSelect
        if timeLeft <= 0:
            return "Request timed out."


def sendOnePing(mySocket, destAddr, ID):
    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    myChecksum = 0
    # Make a dummy header with a 0 checksum.
    # struct -- Interpret strings as packed binary data
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    data = struct.pack("d", time.time())
    # Calculate the checksum on the data and the dummy header.
    myChecksum = checksum(header + data)

    # Get the right checksum, and put in the header
    if sys.platform == 'darwin':
        myChecksum = htons(myChecksum) & 0xffff
    # Convert 16-bit integers from host to network byte order.
    else:
        myChecksum = htons(myChecksum)

    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, myChecksum, ID, 1)
    packet = header + data
    mySocket.sendto(packet, (destAddr, 1))  # AF_INET address must be tuple, not str
    # Both LISTS and TUPLES consist of a number of objects
    # which can be referenced by their position number within the object


def doOnePing(destAddr, timeOut):
    icmp = getprotobyname("icmp")
    # SOCK_RAW is a powerful socket type. For more details: http://sockraw.org/papers/sock_raw
    mySocket = socket(AF_INET, SOCK_RAW, icmp)
    myID = os.getpid() & 0xFFFF  # Return the current process i
    sendOnePing(mySocket, destAddr, myID)
    delay = receiveOnePing(mySocket, myID, timeOut, destAddr)
    mySocket.close()
    return delay


def ping(host, timeOut=1):
    # timeout=1 means: If one second goes by without a reply from the server,
    # the client assumes that either the client's ping or the server's pong is lost
    dest = gethostbyname(host)
    # Initialize variables for report
    numberPacketLost = 0
    numberPacketRecv = 0
    minimumRTT = 99999999
    maximumRTT = 0
    averageRTT = 0
    packetLossRate = 0  # In percentage

    print("Pinging {} ({}) using Python:".format(serverName, dest))
    print("")
    # Send ping requests to a server separated by approximately one second
    for i in range(0, numberPacketSent):
        delay = doOnePing(dest, timeOut)
        if delay == "Request timed out.":  # Packet loss
            numberPacketLost += 1
            print(delay)
        else:  # Packet received successfully
            numberPacketRecv += 1
            delay = round(delay * 1000, 2)  # Convert delay from second to mili-second and round to 2 decimals
            maximumRTT = max(maximumRTT, delay)
            minimumRTT = min(minimumRTT, delay)
            averageRTT = averageRTT + delay
            print("Reply from {}:".format(dest), end="\t")
            print("time = {} ms".format(delay))
        time.sleep(1)  # one second

    packetLossRate = round((numberPacketLost / numberPacketSent) * 100, 2)  # Calc packet lost rate
    averageRTT = round(averageRTT / numberPacketSent, 2)
    # Report for packets
    print("\n--- {} ping statistics ---".format(serverName))
    print("\t" + "Send = {}".format(numberPacketSent), end=", ")
    print("Received = {}".format(numberPacketRecv), end=", ")
    print("Lost = {}".format(numberPacketLost), end=" ")
    print("({}% lost)".format(packetLossRate))

    # Report for RTT
    print("Approximate round trip times in milli-seconds:")
    print("\tMinimum = {} ms".format(minimumRTT), end=", ")
    print("Maximum = {} ms".format(maximumRTT), end=", ")
    print("Average = {} ms".format(averageRTT))


ping(serverName)
