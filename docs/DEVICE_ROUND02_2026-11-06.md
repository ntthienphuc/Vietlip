# Human live test, round 2

Prepared 2026-11-06 for Android 1.4.1+6 on the connected SM-G965F.
The server health check reported ready, CUDA, auto-avsr-vi-so_seed17,
realtime available, and no active batch job. The participant subsequently
confirmed completion and reported that some initially correct words became
incorrect on the next window. Results and the application fix are recorded
in CAPTION_STABILITY_2026-11-06.md.

Keep the phone vertical, face well lit and fully visible, approximately
40-60 cm away. Use ordinary conversational pace; do not exaggerate lip
movements or read the item numbers.

Start live, face the camera silently for 5 seconds, then read these sentences
in order. Pause for 3 seconds between sentences while remaining in frame.

1. Hôm nay tôi muốn thử ứng dụng đọc môi.
2. Bạn có thể giúp tôi được không?
3. Tôi đang kiểm tra camera trên điện thoại.
4. Chiều nay tôi sẽ đi mua một ít trái cây.
5. Ngày mai chúng ta gặp nhau ở trước cổng trường.

After the final sentence remain visible and silent for 6 seconds, then end
the session once. Do not manually flush or stop between sentences. If the
spoken text differs, obtain the actual words before computing WER/CER.

Compare the first three sentences with the preceding physical-device test;
report the two new sentences separately. Preserve original saved video and
captions. Inspect automatic finalization, any text during silence, preview
geometry and logged transport fps. A user's approximate latency observation
is subjective; UI samples or decoder runtime alone do not establish precise
speech-end-to-caption latency. These five prompted sentences are an
application diagnostic, not an independent general-accuracy evaluation.

Automated background UI observation was not started: the tool policy rejected
that launch. Use the app's saved recording/history and available logs after
the participant confirms completion. Do not claim live monitoring occurred.
