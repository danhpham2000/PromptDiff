import "./styles.css";

export const metadata = {
  title: "PromptDiff",
  description: "Git-style diffs for AI behavior",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

