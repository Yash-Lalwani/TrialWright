// Polyfill: async iteration of ReadableStream (`for await (const x of stream)`).
//
// pdf.js 6 reads text content with `for await (... of readableStream)` in
// PDFPageProxy.getTextContent(), which react-pdf calls for every page's text layer.
// Safari 17 (and other browsers without the Streams async-iterator) throws
// "undefined is not a function (near '...value of readableStream...')", and the page
// never renders. pdf.js's legacy build polyfills `Iterator` but not this API.
//
// Installs only when the API is missing. Follows the Streams spec: values() takes
// { preventCancel }, and an early exit (break / return) cancels the stream unless
// preventCancel is set. Remove once the supported browsers all ship it natively.

type StreamIterator<T> = AsyncIterableIterator<T> & { return(value?: unknown): Promise<IteratorResult<T>> };

// TS's DOM lib does not declare the async iterator on ReadableStream, so feature-test untyped.
const streamProto =
  typeof ReadableStream !== "undefined" ? (ReadableStream.prototype as unknown as Record<PropertyKey, unknown>) : null;

if (streamProto && typeof streamProto[Symbol.asyncIterator] !== "function") {
  const values = function <T>(this: ReadableStream<T>, options?: { preventCancel?: boolean }): StreamIterator<T> {
    const reader = this.getReader();
    const preventCancel = Boolean(options?.preventCancel);
    let finished = false;
    const iterator: StreamIterator<T> = {
      async next() {
        if (finished) return { done: true, value: undefined };
        try {
          const result = await reader.read();
          if (result.done) {
            finished = true;
            reader.releaseLock();
          }
          return result as IteratorResult<T>;
        } catch (error) {
          finished = true;
          reader.releaseLock();
          throw error;
        }
      },
      async return(value?: unknown) {
        if (!finished) {
          finished = true;
          const cancelled = preventCancel ? undefined : reader.cancel(value);
          reader.releaseLock();
          await cancelled;
        }
        return { done: true, value: value as T };
      },
      [Symbol.asyncIterator]() {
        return this;
      },
    };
    return iterator;
  };

  if (typeof streamProto.values !== "function") {
    Object.defineProperty(streamProto, "values", { value: values, writable: true, configurable: true });
  }
  Object.defineProperty(streamProto, Symbol.asyncIterator, {
    value: streamProto.values,
    writable: true,
    configurable: true,
  });
}

export {};
