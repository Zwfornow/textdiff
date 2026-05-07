import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "文本对比工作台",
  description: "输入文本或上传文件，生成文本差异报告。",
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}