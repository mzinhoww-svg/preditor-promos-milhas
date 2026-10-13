import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";
import { dataSource } from "@/lib/api";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Preditor de promoções", template: "%s · Preditor de promoções" },
  description:
    "Próximas promoções prováveis de pontos e milhas, com probabilidade calibrada, faixa de bônus e saúde do modelo.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  const source = dataSource();
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#conteudo"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-30 focus:rounded focus:bg-panel focus:px-3 focus:py-2 focus:text-panel-ink"
        >
          Ir para o conteúdo
        </a>
        <Nav source={source} />
        <main id="conteudo" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-16 pt-6 sm:px-6 lg:px-8">
          {children}
        </main>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-ink-3 sm:px-6 lg:px-8">
            <span>Preditor de promoções de milhas · dashboard v0</span>
            <span>Horários em UTC. Probabilidades calibradas pelo modelo em produção.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
