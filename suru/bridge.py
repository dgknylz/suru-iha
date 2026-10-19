"""Python -> Unity köprüsü. Her kareyi JSON olarak UDP ile yollar.

UDP seçtik çünkü: kare kaybolursa bir sonraki gelir, beklemek yok (gerçek zamanlı görüntü için ideal).
"""
import json
import socket


class UnityBridge:
    def __init__(self, host="127.0.0.1", port=5065):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, frame: dict):
        data = json.dumps(frame, separators=(",", ":")).encode("utf-8")
        self.sock.sendto(data, self.addr)
