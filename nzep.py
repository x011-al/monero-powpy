import socket
import json
import struct
import binascii
import random
import time
import randomx  # Menggunakan pustaka python-randomx

# Fungsi untuk menghubungkan ke pool dan login
def login_to_pool(pool_address, wallet_address):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(pool_address)
    login_message = json.dumps({
        'method': 'login',
        'params': {'login': wallet_address, 'pass': 'x', 'agent': 'PythonMiner'},
        'id': 1
    })
    s.sendall((login_message + '\n').encode('utf-8'))
    response = s.recv(1024).decode('utf-8')
    print(response)
    return s

# Fungsi untuk menerima pekerjaan mining dari pool
def get_new_job(socket):
    job_message = json.dumps({
        'method': 'getjob',
        'params': [],
        'id': 1
    })
    socket.sendall((job_message + '\n').encode('utf-8'))
    response = socket.recv(1024).decode('utf-8')
    job_data = json.loads(response)
    print(f"Received new job: {job_data}")
    return job_data['result']

# Fungsi untuk meng-hash dengan RandomX
def process_job(job):
    blob = job.get('blob')
    target = job.get('target')
    job_id = job.get('job_id')
    height = job.get('height')

    print(f"Processing job {job_id} at height {height} with target {target}")

    # Jika menggunakan algoritma RandomX, panggil fungsi hashing
    try:
        # Menggunakan randomx untuk hashing
        seed_hash = binascii.unhexlify(blob[:64])  # Mengambil seed hash dari blob
        hash_result = randomx.get_hash(seed_hash)  # Hash dengan RandomX
        print(f"Hash result: {binascii.hexlify(hash_result)}")
    except Exception as e:
        print(f"Error hashing with RandomX: {e}")
        return None

    # Verifikasi hasil hash dengan target
    r64 = struct.unpack('Q', hash_result[24:])[0]
    target_int = struct.unpack('I', binascii.unhexlify(target))[0]

    # Bandingkan hash dengan target
    if r64 < target_int:
        print(f"Hash found for job {job_id}: {binascii.hexlify(hash_result)}")
        submit_hash_result(job_id, hash_result)
    else:
        print(f"Hash did not meet target for job {job_id}")

# Fungsi untuk mengirim hasil hash ke pool
def submit_hash_result(job_id, hash_result):
    submit_message = {
        'method': 'submit',
        'params': {
            'job_id': job_id,
            'nonce': binascii.hexlify(hash_result[:4]).decode(),
            'result': binascii.hexlify(hash_result).decode(),
        },
        'id': 1
    }
    print(f"Submitting result: {submit_message}")
    # Kirimkan hasil ke pool (gunakan socket yang terbuka untuk mengirim hasilnya)
    # s.sendall(str(json.dumps(submit_message) + '\n').encode('utf-8'))

# Fungsi utama untuk menjalankan proses mining
def run_mining():
    pool_address = ('ebelete-38128.portmap.host', 38128)  # Ganti dengan alamat pool yang sesuai
    wallet_address = 'your_wallet_address_here'  # Ganti dengan alamat wallet Anda

    # Login ke pool
    s = login_to_pool(pool_address, wallet_address)

    while True:
        # Ambil job baru
        job = get_new_job(s)

        # Proses job
        process_job(job)

        # Tunggu sebelum mengambil job berikutnya
        time.sleep(10)  # Sesuaikan dengan interval yang diinginkan

if __name__ == '__main__':
    run_mining()
