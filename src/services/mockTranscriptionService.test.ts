import { act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { startMockTranscription } from './mockTranscriptionService';

afterEach(() => {
  vi.useRealTimers();
});

describe('mock transcription service', () => {
  it('emits interim revisions then a final event using one segment ID', () => {
    vi.useFakeTimers();
    const onEvent = vi.fn();
    startMockTranscription(onEvent);

    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent.mock.calls[0][0]).toMatchObject({
      type: 'user',
      segmentId: 'mock-live-segment-1',
      isFinal: false,
      revision: 1,
      confidence: 0.94,
      speaker: 'You',
      text: 'I would like to plan',
    });
    expect(onEvent.mock.calls[0][0].revisedAt).toBeUndefined();
    expect(onEvent.mock.calls[0][0]).not.toHaveProperty('contextSources');
    expect(onEvent.mock.calls[0][0]).not.toHaveProperty('screenContext');

    act(() => vi.advanceTimersByTime(1400));
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls[1][0]).toMatchObject({
      segmentId: 'mock-live-segment-1',
      isFinal: false,
      revision: 2,
      confidence: 0.94,
      revisedAt: onEvent.mock.calls[1][0].timestamp,
      text: 'I would like to plan a small team workshop',
    });

    act(() => vi.advanceTimersByTime(1400));
    expect(onEvent.mock.calls[2][0]).toMatchObject({
      segmentId: 'mock-live-segment-1',
      isFinal: false,
      revision: 3,
      confidence: 0.94,
      text: 'I would like to plan a small team workshop for next week',
    });

    act(() => vi.advanceTimersByTime(1400));
    expect(onEvent).toHaveBeenCalledTimes(4);
    expect(onEvent.mock.calls[3][0]).toMatchObject({
      segmentId: 'mock-live-segment-1',
      isFinal: true,
      revision: 4,
      confidence: 0.94,
      text: 'I would like to plan a small team workshop for next week.',
    });
    onEvent.mock.calls.forEach(([event]) => {
      expect(event).not.toHaveProperty('contextSources');
      expect(event).not.toHaveProperty('screenContext');
      expect(event.text).not.toMatch(/screen context|screen capture|screen contents/i);
    });
    expect(new Date(onEvent.mock.calls[0][0].timestamp).toISOString()).toBe(
      onEvent.mock.calls[0][0].timestamp,
    );
    expect(new Date(onEvent.mock.calls[3][0].timestamp).toISOString()).toBe(
      onEvent.mock.calls[3][0].timestamp,
    );
  });

  it('omits confidence when the source fixture does not provide it', () => {
    vi.useFakeTimers();
    const onEvent = vi.fn();
    startMockTranscription(onEvent, {});

    expect(onEvent.mock.calls[0][0]).not.toHaveProperty('confidence');
    act(() => vi.advanceTimersByTime(4200));
    expect(onEvent).toHaveBeenCalledTimes(4);
    onEvent.mock.calls.forEach(([event]) => {
      expect(event).not.toHaveProperty('confidence');
    });
  });

  it('stops emitting when the stream is cancelled', () => {
    vi.useFakeTimers();
    const onEvent = vi.fn();
    const stop = startMockTranscription(onEvent);

    stop();
    act(() => vi.advanceTimersByTime(5000));

    expect(onEvent).toHaveBeenCalledTimes(1);
  });
});
