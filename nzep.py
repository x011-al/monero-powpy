import socket
import struct
import json
import binascii
import time
import sys
import os
import select
from multiprocessing import Process, Queue

import pyrx  # Pastikan anda sudah menginstal pyrx untuk hashing RandomX

# Fungsi untuk mem-packing nonce ke dalam format yang tepat
def pack_nonce(blob, nonce):
    nonce_pack = struct.pack('<I', nonce)
    return blob[:39] + nonce_pack + blob[43:]

# Fungsi untuk worker dalam proses mining
def worker(q, s, nicehash=False):
    started = time.time()
    hash_count = 0

    while True:
        job = q.get()  # Ambil pekerjaan baru dari antrian
        if job.get('login_id'):
            login_id = job.get('login_id')
            print(f'Login ID: {login_id}')

        blob = job.get('blob')
        target = job.get('target')
        job_id = job.get('job_id')
        height = job.get('height')
        block_major = int(blob[:2], 16)
        cnv = 0
        seed_hash = None  # Inisialisasi seed_hash sebelum digunakan

        # Tentukan CNv untuk algoritma RandomX
        if block_major >= 7:
            cnv = block_major - 6
        if cnv > 5:
            seed_hash = binascii.unhexlify(job.get('seed_hash'))
            print(f'New job with target: {target}, RandomX, height: {height}')
        else:
            print(f'New job with target: {target}, CNv{cnv}, height: {height}')

        target = struct.unpack('I', binascii.unhexlify(target))[0]
        if target >> 32 == 0:
            target = int(0xFFFFFFFFFFFFFFFF / int(0xFFFFFFFF / target))

        nonce = 1
        while True:
            bin = pack_nonce(blob, nonce)  # Pack nonce ke dalam blob

            if cnv > 5:
                # Menggunakan algoritma RandomX
                if seed_hash is not None:
                    hash_result = pyrx.get_rx_hash(bin, seed_hash, height)  # Menghitung hash menggunakan pyrx
                else:
                    print("Error: seed_hash is not defined!")
                    continue  # Lewatkan jika seed_hash belum didefinisikan
            else:
                # Jika algoritma selain RandomX, lanjutkan tanpa pemrosesan hash
                print("Processing with non-RandomX algorithm (not implemented here).")
                continue

            if hash_result is not None:
                hash_count += 1
                sys.stdout.write('.')
                sys.stdout.flush()

                # Mengkonversi hasil hash menjadi hex
                hex_hash = binascii.hexlify(hash_result).decode()

                # Mengambil 64-bit nilai dari hash untuk dibandingkan dengan target
                r64 = struct.unpack('Q', hash_result[24:])[0]

                # Jika hash lebih kecil dari target, berarti valid
                if r64 < target:
                    elapsed = time.time() - started
                    hr = int(hash_count / elapsed)
                    print(f'{os.linesep}Hashrate: {hr} H/s')

                    # Jika menggunakan NiceHash, ekstrak nonce
                    if nicehash:
                        nonce = struct.unpack('I', bin[39:43])[0]

                    # Menyiapkan dan mengirim hasil ke pool
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
                    print(f'Submitting hash: {hex_hash}')
                    s.sendall(str(json.dumps(submit) + '\n').encode('utf-8'))
                    select.select([s], [], [], 3)

                    # Keluar dari loop jika antrian pekerjaan kosong
                    if not q.empty():
                        break

            # Increment nonce dan lanjutkan
            nonce += 1

# Fungsi untuk menghubungkan ke pool dan memulai proses mining
def connect_to_pool():
    pool_host = "ebelete-38128.portmap.host"
    pool_port = 38128
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((pool_host, pool_port))
    s.settimeout(5)

    # Kirim metode 'login' untuk memulai
    login_message = {
        'method': 'login',
        'params': {
            'login': 'ZEPHYR2bfuCKz4kS5XpXWqPhrdUyKkLQSR6t9D7xmn1LHtto15kuvkFCHckMXaGVt8ML4VPCcNgsBN2MXcv78NPAerJ6DV2gWim3h',  # Gantilah dengan login yang valid
            'pass': 'x',
            'agent': 'python-miner'
        },
        'id': 1
    }

    s.sendall(str(json.dumps(login_message) + '\n').encode('utf-8'))

    # Terima respon login
    response = s.recv(4096).decode()
    print(f"Login response: {response}")

    # Tunggu job baru
    while True:
        data = s.recv(4096).decode()
        if data:
            job = json.loads(data)
            if 'method' in job and job['method'] == 'job':
                q.put(job['params'])  # Masukkan pekerjaan ke dalam antrian untuk diproses

# Fungsi utama untuk menjalankan mining
if __name__ == "__main__":
    q = Queue()  # Antrian pekerjaan
    pool_process = Process(target=connect_to_pool)  # Proses untuk menghubungkan ke pool
    mining_process = Process(target=worker, args=(q, s))  # Proses untuk menangani mining

    pool_process.start()  # Mulai proses untuk menghubungkan ke pool
    mining_process.start()  # Mulai proses mining

    pool_process.join()  # Menunggu proses koneksi pool selesai
    mining_process.join()  # Menunggu proses mining selesai
