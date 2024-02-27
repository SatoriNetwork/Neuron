import libtorrent as lt
import time


def create_and_seed_torrent(file_path, save_path):
    fs = lt.file_storage()
    lt.add_files(fs, file_path)
    t = lt.create_torrent(fs)
    # Optional: Use if you have a tracker
    t.add_tracker("http://yourtracker.com/announce")
    t.set_creator('My Torrent Creator')
    lt.set_piece_hashes(t, save_path)
    torrent = t.generate()
    torrent_file_path = save_path + "/my_torrent.torrent"
    with open(torrent_file_path, "wb") as f:
        f.write(lt.bencode(torrent))

    # Start seeding
    ses = lt.session()
    ses.listen_on(6881, 6891)
    info = lt.torrent_info(torrent)
    h = ses.add_torrent({'ti': info, 'save_path': save_path})
    print(f"Seeding {file_path} at {torrent_file_path}")

    # Seeding indefinitely; in practice, you might seed for a certain duration or until a condition is met
    while True:
        s = h.status()
        print(
            f'Download rate: {s.download_rate / 1000} kB/s, Upload rate: {s.upload_rate / 1000} kB/s, Peers: {s.num_peers}')
        time.sleep(5)


create_and_seed_torrent('/path/to/your/content',
                        '/path/where/torrent/is/saved')
