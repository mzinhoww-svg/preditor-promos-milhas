"use client";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-lg py-16 text-center">
      <h1 className="text-xl font-semibold text-ink">Não foi possível carregar os dados</h1>
      <p className="mt-2 text-sm leading-6 text-ink-2">
        A API não respondeu ou a configuração está incompleta. Confira as variáveis de ambiente no servidor.
      </p>
      {error.digest ? <p className="mt-2 font-mono text-xs text-ink-3">ref. {error.digest}</p> : null}
      <button
        type="button"
        onClick={reset}
        className="mt-6 rounded-md bg-ink px-4 py-2 text-sm font-medium text-bg transition-colors duration-150 hover:bg-panel-2"
      >
        Tentar de novo
      </button>
    </div>
  );
}
