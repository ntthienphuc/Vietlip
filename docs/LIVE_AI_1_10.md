# Captions and sentence suggestions

**Live captions** (*Phụ đề trực tiếp*) is the default mode. SO17 reads overlapping video windows on the PC. The app can show a phrase as soon as consecutive windows agree. The server uses visible mouth activity to decide when to finalize a segment.

**Sentence suggestions** (*Kèm gợi ý câu*) use the same visual caption. Once the server finalizes a segment, it can send that text to Gemini 3.1 Flash-Lite. The phone keeps the original above the suggestion and associates both with the same segment. The user can keep speaking while the request is pending. If Gemini is unavailable or its quota is exhausted, the original caption remains available.

## Enable suggestions

1. If you installed the preconfigured EXE from the private distribution package, the installer sets up a key on a fresh Windows profile. For a build from GitHub, open **VietLip Server → Cài đặt key Gemini** on the PC, paste your own key, and save it. Windows protects the saved key with DPAPI for the current account. Updates preserve that setting.
2. On Android, open **Cài đặt → Cách đọc môi → Kèm gợi ý câu → Áp dụng** (settings → reading mode → include sentence suggestions → apply).
3. Start a new session. The Android client communicates with the PC over the LAN. The PC needs internet access to request suggestions.

Session history keeps both readings for comparison. Names, numbers, and negation can change the meaning of a sentence. Confirm these with the speaker when they matter.
