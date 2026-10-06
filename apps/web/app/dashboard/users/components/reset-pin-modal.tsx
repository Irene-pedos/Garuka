"use client";

import { AccessibleModal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { UserItem } from "@/lib/api/client";
import { KeyRound, Smartphone } from "lucide-react";

interface ResetPinModalProps {
  user: UserItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  loading: boolean;
}

export function ResetPinModal({
  user,
  isOpen,
  onClose,
  onConfirm,
  loading,
}: ResetPinModalProps) {
  if (!user) return null;

  return (
    <AccessibleModal
      isOpen={isOpen}
      onClose={onClose}
      title="Reset USSD PIN"
      description="Clear existing mobile dialing credentials."
      maxWidth="sm"
    >
      <div className="space-y-4 pt-1">
        <div className="p-3 bg-muted/40 rounded-lg border space-y-1.5 text-xs">
          <div className="font-semibold text-foreground text-sm flex items-center gap-1.5">
            <KeyRound className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <span>{user.full_name}</span>
          </div>
          <div className="text-muted-foreground flex items-center gap-1.5 font-mono">
            <Smartphone className="h-3.5 w-3.5" />
            <span>{user.phone_masked || "No phone registered"}</span>
          </div>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed">
          Are you sure you want to reset this staff member's USSD PIN? Their existing PIN will be cleared. On their next call to the gateway (<span className="font-mono text-[11px]">*384*...#</span>), they will be prompted to create a new 4-digit PIN.
        </p>

        <div className="flex justify-end gap-2 pt-2 border-t">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant="destructive" size="sm" onClick={onConfirm} disabled={loading}>
            {loading ? "Resetting..." : "Reset USSD PIN"}
          </Button>
        </div>
      </div>
    </AccessibleModal>
  );
}
