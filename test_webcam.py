import cv2
import time
import sys

def test_discovery():
    print("=== AYZARA WEBCAM DIAGNOSTIC TOOL ===")
    print("Mencari kamera lokal (0-10)...")
    
    available_cameras = []
    
    # Prioritas Backend
    backends = [
        ("DirectShow (DSHOW)", cv2.CAP_DSHOW),
        ("Media Foundation (MSMF)", cv2.CAP_MSMF),
        ("Default (ANY)", cv2.CAP_ANY)
    ]
    
    for i in range(10):
        found_any_backend = False
        print(f"\n[Index {i}] Mengecek...")
        
        for name, backend in backends:
            try:
                cap = cv2.VideoCapture(i, backend)
                if cap and cap.isOpened():
                    # Tunggu sinkronisasi driver
                    time.sleep(0.5)
                    ret, frame = cap.read()
                    
                    if ret:
                        print(f"  [SUCCESS] Terdeteksi via {name}")
                        available_cameras.append((i, name))
                        found_any_backend = True
                        cap.release()
                        break
                    else:
                        print(f"  [FAILED ] Terbuka via {name} tapi gagal baca frame")
                    cap.release()
                else:
                    print(f"  [SKIP   ] Tidak dapat membuka via {name}")
            except Exception as e:
                print(f"  [ERROR  ] Exception via {name}: {e}")
        
        if not found_any_backend:
            print(f"[Index {i}] Tidak ada kamera yang ditemukan.")

    print("\n" + "="*35)
    if not available_cameras:
        print("HASIL: TIDAK ADA KAMERA DITEMUKAN")
        print("Saran: Cek Device Manager atau coba port USB lain.")
    else:
        print(f"HASIL: Ditemukan {len(available_cameras)} kamera:")
        for idx, bname in available_cameras:
            print(f" - Index {idx} ({bname})")
    print("="*35)

if __name__ == "__main__":
    test_discovery()
