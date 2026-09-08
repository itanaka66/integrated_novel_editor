import "./globals.css";

export const metadata = {
  title: "AI Novel Studio",
  description: "AI-powered long-form novel development environment",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
