from app.services.caption_delivery import CaptionDelivery


def test_receipts_bound_network_and_frame_time_and_reject_replays():
    clock = [10.]
    delivery = CaptionDelivery(lambda: clock[0])
    payload = dict(type='segment_final', transcript='xin chào', turn_id=1,
                   window_end=5., capture_clock_seconds=7.)
    delivery.stamp(payload)
    clock[0] += .08
    message = dict(caption_event_id=payload['caption_event_id'], receive_to_frame_ms=16.)
    result = delivery.acknowledge(message)
    assert result['caption_changed']
    assert result['server_send_to_render_ack_ms'] == 80
    assert result['window_end_to_render_ack_ms'] == 2080
    assert result['receive_to_flutter_frame_ms'] == 16
    assert delivery.acknowledge(message) is None


def test_bad_diagnostics_do_not_crash_or_grow_session_state():
    delivery = CaptionDelivery(lambda: 0.)
    for _ in range(100):
        delivery.stamp(dict(type='partial', transcript='xin'))
    assert len(delivery.pending) == 64
    for invalid in (None, '10', True, float('nan'), float('inf'), -1, 60001):
        assert delivery.acknowledge(dict(caption_event_id=100, receive_to_frame_ms=invalid)) is None
    assert delivery.acknowledge(dict(caption_event_id=1, receive_to_frame_ms=0)) is None
    assert delivery.acknowledge(dict(caption_event_id=True, receive_to_frame_ms=0)) is None
    assert delivery.acknowledge(dict(caption_event_id=100, receive_to_frame_ms=100)) is None


def test_unchanged_caption_and_noncaption_events_are_explicit():
    delivery = CaptionDelivery(lambda: 0.)
    for event in ('ready', 'telemetry', 'ack', 'session_final'):
        payload = dict(type=event)
        delivery.stamp(payload)
        assert 'caption_event_id' not in payload
    for i in range(2):
        payload = dict(type='partial', transcript='xin')
        delivery.stamp(payload)
        result = delivery.acknowledge(dict(caption_event_id=payload['caption_event_id'], receive_to_frame_ms=0))
        assert result['caption_changed'] == (i == 0)
        assert result['window_end_to_render_ack_ms'] is None
