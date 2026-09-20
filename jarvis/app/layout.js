import './globals.css';

export const metadata = {
  title: 'InfoSphere // Jarvis Dashboard',
  description: 'Local system observability dashboard',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
