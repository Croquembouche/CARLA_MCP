import socket,sys,struct
port=int(sys.argv[1]);cmd=' '.join(sys.argv[2:]).encode()
def string(b):return b'\xdb'+struct.pack('>I',len(b))+b
with socket.create_connection(('127.0.0.1',port),timeout=60) as s:
 s.sendall(b'\x94\x00\x01'+string(b'console_command')+b'\x92\x91\xc2'+string(cmd));print(s.recv(65536).hex())
