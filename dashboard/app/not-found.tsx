import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg py-16 text-center">
      <h1 className="text-xl font-semibold text-ink">Página não encontrada</h1>
      <p className="mt-2 text-sm text-ink-2">
        <Link href="/" className="font-medium text-primary underline underline-offset-2">
          Voltar às previsões
        </Link>
      </p>
    </div>
  );
}
