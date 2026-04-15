import { useState, useEffect } from "react";

/* ── Typing Text Animation ── */
export default function TypingText() {
  const phrases = [
    "Map your team's hidden expertise",
    "AI-powered knowledge discovery",
    "Connect minds, amplify intelligence",
    "Your team's second brain",
    "Where knowledge becomes power",
  ];
  const [current, setCurrent] = useState(0);
  const [text, setText] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    const phrase = phrases[current];
    const timeout = setTimeout(
      () => {
        if (!isDeleting) {
          setText(phrase.slice(0, text.length + 1));
          if (text.length + 1 === phrase.length) {
            setTimeout(() => setIsDeleting(true), 2000);
          }
        } else {
          setText(phrase.slice(0, text.length - 1));
          if (text.length === 0) {
            setIsDeleting(false);
            setCurrent((c) => (c + 1) % phrases.length);
          }
        }
      },
      isDeleting ? 30 : 60,
    );
    return () => clearTimeout(timeout);
  }, [text, isDeleting, current]);

  return (
    <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400">
      {text}
      <span className="animate-pulse text-violet-400">|</span>
    </span>
  );
}
