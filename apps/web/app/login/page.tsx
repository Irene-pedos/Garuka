import Link from "next/link";
import { School } from "lucide-react";
import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 self-center font-bold tracking-tight text-foreground transition-opacity hover:opacity-90"
        >
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <School className="size-4.5" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-base font-bold text-primary leading-tight">Garuka</span>
            <span className="text-[10px] text-muted-foreground font-normal tracking-wide">
              Dropout Early-Warning
            </span>
          </div>
        </Link>
        <LoginForm />
      </div>
    </div>
  );
}
