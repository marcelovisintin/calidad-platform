import { useLayoutEffect, useRef } from "react";
import type { TextareaHTMLAttributes } from "react";

type AutoResizeTextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  minHeightPx?: number;
};

export function AutoResizeTextarea({ minHeightPx = 96, style, value, ...props }: AutoResizeTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const adjustHeight = () => {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.max(minHeightPx, textarea.scrollHeight)}px`;
    };

    adjustHeight();
    const observer = new ResizeObserver(adjustHeight);
    observer.observe(textarea);
    return () => observer.disconnect();
  }, [minHeightPx, value]);

  return (
    <textarea
      {...props}
      ref={textareaRef}
      style={{ ...style, minHeight: minHeightPx, overflowY: "hidden", resize: "none" }}
      value={value}
    />
  );
}
