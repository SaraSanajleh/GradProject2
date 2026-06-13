"use client";

import { useState, useEffect } from "react";

interface TypingMessageProps {
  text: string;
  speed?: number;
}

export function TypingMessage({ text, speed = 20 }: TypingMessageProps) {
  const [display, setDisplay] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDone(false);
  }, [text]);

  useEffect(() => {
    if (done) {
      setDisplay(text);
      return;
    }
    let i = 0;
    setDisplay("");
    const t = setInterval(() => {
      i++;
      setDisplay(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(t);
        setDone(true);
      }
    }, speed);
    return () => clearInterval(t);
  }, [text, speed, done]);

  return <span className="whitespace-pre-wrap">{display}</span>;
}
