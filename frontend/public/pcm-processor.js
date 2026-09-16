/**
 * PCM Processor — AudioWorklet for microphone capture
 *
 * Converts Float32 audio from the microphone to Int16 PCM (mono, 24 kHz target).
 * Resamples from the browser's native rate if needed (handles Firefox + Safari).
 *
 * This file must be served as a static asset — place in /public/pcm-processor.js.
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { inputSampleRate = 24000, targetSampleRate = 24000 } =
      options?.processorOptions ?? {};
    this.ratio = inputSampleRate / targetSampleRate;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;

    const outLength = Math.floor(input.length / this.ratio);
    const pcm16 = new Int16Array(outLength);

    for (let i = 0; i < outLength; i++) {
      const sample = input[Math.floor(i * this.ratio)] ?? 0;
      pcm16[i] = Math.max(-32768, Math.min(32767, Math.round(sample * 32767)));
    }

    // Transfer buffer (zero-copy)
    this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    return true;
  }
}

registerProcessor("pcm-processor", PCMProcessor);
