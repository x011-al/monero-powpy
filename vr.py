import argparse
import socket
import select
import binascii
import pycryptonight
import pyrx
import struct
import json
import sys
import os
import time
from multiprocessing import Process, Queue

pool_host = 'ap.luckpool.net'
pool_port = 3960
pool_pass = 'x'
wallet_address = 'RP6jeZhhHiZmzdufpXHCWjYVHsLaPXARt1.us1'
nicehash = False

def main():
    while True:
        try:
            pool_ip = socket.gethostbyname(pool_host)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((pool_ip, pool_port))
            print("Connected to pool:", pool_host)

            q = Queue()
            proc = Process(target=worker, args=(q, s))
            proc.daemon = True
            proc.start()

            login = {
                'method': 'login',
                'params': {
                    'login': wallet_address,
                    'pass': pool_pass,
                    'rigid': '',
                    'agent': 'verus-miner-py/0.1'
                },
                'id': 1
            }
            
            print('Logging into pool: {}:{}'.format(pool_host, pool_port))
            print('Using NiceHash mode: {}'.format(nicehash))
            s.sendall(str(json.dumps(login) + '\n').encode('utf-8'))

            while True:
                line = s.makefile().readline().strip()
                if not line:
                    print("Empty line received from pool. Waiting for the next line...")
                    time.sleep(1)
                    continue

                try:
                    print("Raw response:", line)
                    r = json.loads(line)
                except json.JSONDecodeError:
                    print("Failed to decode JSON from pool response:", line)
                    continue

                if 'error' in r and r['error'] is not None:
                    print('Error: {}'.format(r['error']))
                    continue

                result = r.get('result')
                method = r.get('method')
                params = r.get('params')

                if isinstance(result, dict) and 'job' in result:
                    # Jika pekerjaan baru diterima, proses pekerjaan
                    login_id = result.get('id')
                    job = result.get('job')
                    job['login_id'] = login_id
                    q.put(job)
                elif result is True:
                    # Jika result True tanpa pekerjaan, tunggu respons berikutnya
                    print("No job received yet. Waiting for job assignment from pool...")
                    time.sleep(2)
                elif method == 'job' and 'login_id' in locals():
                    q.put(params)
        except (socket.timeout, socket.error) as e:
            print(f"Connection error: {e}. Retrying connection in 5 seconds...")
            time.sleep(5)
        finally:
            s.close()

def pack_nonce(blob, nonce):
    b = binascii.unhexlify(blob)
    bin = struct.pack('39B', *bytearray(b[:39]))
    if nicehash:
        bin += struct.pack('I', nonce & 0x00ffffff)[:3]
        bin += struct.pack('{}B'.format(len(b)-42), *bytearray(b[42:]))
    else:
        bin += struct.pack('I', nonce)
        bin += struct.pack('{}B'.format(len(b)-43), *bytearray(b[43:]))
    return bin

def worker(q, s):
    started = time.time()
    hash_count = 0

    while True:
        job = q.get()
        if job.get('login_id'):
            login_id = job.get('login_id')
            print('Login ID: {}'.format(login_id))
        blob = job.get('blob')
        target = job.get('target')
        job_id = job.get('job_id')
        height = job.get('height')
        block_major = int(blob[:2], 16)
        cnv = 0
        if block_major >= 7:
            cnv = block_major - 6
        if cnv > 5:
            seed_hash = binascii.unhexlify(job.get('seed_hash'))
            print('New job with target: {}, RandomX, height: {}'.format(target, height))
        else:
            print('New job with target: {}, CNv{}, height: {}'.format(target, cnv, height))
        target = struct.unpack('I', binascii.unhexlify(target))[0]
        if target >> 32 == 0:
            target = int(0xFFFFFFFFFFFFFFFF / int(0xFFFFFFFF / target))
        nonce = 1

        while True:
            bin = pack_nonce(blob, nonce)
            if cnv > 5:
                hash = pyrx.get_rx_hash(bin, seed_hash, height)
            else:
                hash = pycryptonight.cn_slow_hash(bin, cnv, 0, height)
            hash_count += 1
            sys.stdout.write('.')
            sys.stdout.flush()
            hex_hash = binascii.hexlify(hash).decode()
            r64 = struct.unpack('Q', hash[24:])[0]
            if r64 < target:
                elapsed = time.time() - started
                hr = int(hash_count / elapsed)
                print('{}Hashrate: {} H/s'.format(os.linesep, hr))
                if nicehash:
                    nonce = struct.unpack('I', bin[39:43])[0]
                submit = {
                    'method': 'submit',
                    'params': {
                        'id': login_id,
                        'job_id': job_id,
                        'nonce': binascii.hexlify(struct.pack('<I', nonce)).decode(),
                        'result': hex_hash
                    },
                    'id': 1
                }
                print('Submitting hash: {}'.format(hex_hash))
                s.sendall(str(json.dumps(submit) + '\n').encode('utf-8'))
                select.select([s], [], [], 3)
                if not q.empty():
                    break
            nonce += 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--nicehash', action='store_true', help='NiceHash mode')
    parser.add_argument('--host', action='store', help='Pool host')
    parser.add_argument('--port', action='store', help='Pool port')
    args = parser.parse_args()
    if args.nicehash:
        nicehash = True
    if args.host:
        pool_host = args.host
    if args.port:
        pool_port = int(args.port)
    main()
