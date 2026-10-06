"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  updateProfile,
  changePassword,
  changePin,
  uploadAvatar,
  type UserMeResponse,
} from "@/lib/api/client";
import { ScopeHeader } from "@/components/scope-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { toast } from "sonner";
import {
  User,
  Camera,
  Mail,
  Phone,
  Globe,
  Building2,
  ShieldCheck,
  KeyRound,
  Lock,
  Hash,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Copy,
  Check,
  Trash2,
  Clock,
  Sparkles,
} from "lucide-react";

export default function AccountPage() {
  const { user, refreshUser } = useAuth();

  // Profile Form State
  const [fullName, setFullName] = useState("");
  const [phoneE164, setPhoneE164] = useState("");
  const [language, setLanguage] = useState<"rw" | "en" | "fr">("rw");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Avatar Upload State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);

  // Password Form State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  // USSD PIN Form State
  const [currentPin, setCurrentPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [isChangingPin, setIsChangingPin] = useState(false);
  const [pinSuccess, setPinSuccess] = useState<string | null>(null);
  const [pinError, setPinError] = useState<string | null>(null);

  // Copy User ID state
  const [copiedId, setCopiedId] = useState(false);

  // Initialize fields when user is loaded
  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setPhoneE164(user.phone_e164 || "");
      setLanguage((user.language as "rw" | "en" | "fr") || "rw");
    }
  }, [user]);

  if (!user) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const initials = user.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "GK";

  // Handle Profile Save
  const handleProfileSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileError(null);
    setProfileSuccess(null);

    if (!fullName.trim()) {
      setProfileError("Full name is required.");
      return;
    }

    if (phoneE164.trim() && !/^\+[1-9]\d{6,14}$/.test(phoneE164.trim())) {
      setProfileError(
        "Phone number must be in E.164 format (e.g. +250788123456)."
      );
      return;
    }

    setIsSavingProfile(true);
    try {
      await updateProfile({
        full_name: fullName.trim(),
        phone_e164: phoneE164.trim() || undefined,
        language,
      });
      await refreshUser();
      setProfileSuccess("Profile details updated successfully.");
      toast.success("Profile updated successfully");
    } catch (err: any) {
      const msg = err.message || "Failed to update profile";
      setProfileError(msg);
      toast.error(msg);
    } finally {
      setIsSavingProfile(false);
    }
  };

  // Handle Avatar Upload
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      toast.error("Avatar image must be smaller than 2MB.");
      return;
    }

    setIsUploadingAvatar(true);
    try {
      await uploadAvatar(file);
      await refreshUser();
      toast.success("Profile photo updated successfully!");
    } catch (err: any) {
      toast.error(err.message || "Failed to upload avatar");
    } finally {
      setIsUploadingAvatar(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Handle Remove Avatar
  const handleRemoveAvatar = async () => {
    setIsUploadingAvatar(true);
    try {
      await updateProfile({ avatar_url: "" });
      await refreshUser();
      toast.success("Profile photo removed.");
    } catch (err: any) {
      toast.error(err.message || "Failed to remove avatar");
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  // Handle Password Change
  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!currentPassword) {
      setPasswordError("Please enter your current password.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation do not match.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSuccess("Password changed successfully.");
      toast.success("Password changed successfully");
    } catch (err: any) {
      const msg = err.message || "Failed to update password";
      setPasswordError(msg);
      toast.error(msg);
    } finally {
      setIsChangingPassword(false);
    }
  };

  // Handle USSD PIN Change
  const handlePinChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPinError(null);
    setPinSuccess(null);

    if (!/^\d{4}$/.test(newPin)) {
      setPinError("New USSD PIN must be exactly 4 numeric digits.");
      return;
    }
    if (newPin !== confirmPin) {
      setPinError("New PIN and confirmation do not match.");
      return;
    }

    setIsChangingPin(true);
    try {
      await changePin({
        current_pin: currentPin ? currentPin : undefined,
        new_pin: newPin,
      });
      setCurrentPin("");
      setNewPin("");
      setConfirmPin("");
      setPinSuccess("USSD PIN changed successfully.");
      toast.success("USSD PIN updated successfully");
    } catch (err: any) {
      const msg = err.message || "Failed to update USSD PIN";
      setPinError(msg);
      toast.error(msg);
    } finally {
      setIsChangingPin(false);
    }
  };

  const handleCopyId = () => {
    navigator.clipboard.writeText(user.id);
    setCopiedId(true);
    toast.info("User ID copied to clipboard");
    setTimeout(() => setCopiedId(false), 2000);
  };

  const roleFormatted = user.role.replace(/_/g, " ");

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      <ScopeHeader
        title="Account Settings"
        description="Manage your profile information, regional assignment, login credentials, and USSD mobile PIN."
      />

      {/* Profile Overview Header Card */}
      <Card className="border shadow-xs">
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
            {/* Avatar Section */}
            <div className="relative group shrink-0">
              <Avatar className="size-24 rounded-2xl ring-2 ring-primary/20 shadow-md">
                {user.avatar_url && (
                  <AvatarImage
                    src={user.avatar_url}
                    alt={user.full_name}
                    className="object-cover"
                  />
                )}
                <AvatarFallback className="text-xl font-bold rounded-2xl bg-primary/10 text-primary">
                  {initials}
                </AvatarFallback>
              </Avatar>

              {/* Upload Overlay Button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingAvatar}
                aria-label="Upload photo"
                className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl bg-black/50 text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer disabled:pointer-events-none"
              >
                {isUploadingAvatar ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Camera className="w-5 h-5 mb-1" />
                    <span className="text-[10px] font-medium">Change</span>
                  </>
                )}
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

            {/* Profile Summary Info */}
            <div className="flex-1 text-center sm:text-left space-y-2">
              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2.5">
                <h2 className="text-xl font-bold tracking-tight text-foreground">
                  {user.full_name}
                </h2>
                <Badge
                  variant="outline"
                  className="capitalize font-semibold text-xs bg-primary/10 text-primary border-primary/20 px-2.5 py-0.5"
                >
                  <ShieldCheck className="w-3.5 h-3.5 mr-1" />
                  {roleFormatted}
                </Badge>
                {user.is_active && (
                  <Badge
                    variant="outline"
                    className="text-xs bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                  >
                    Active Account
                  </Badge>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-4 text-xs text-muted-foreground pt-0.5">
                {user.email && (
                  <span className="flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-muted-foreground/80" />
                    {user.email}
                  </span>
                )}
                {user.phone_e164 && (
                  <span className="flex items-center gap-1.5">
                    <Phone className="w-3.5 h-3.5 text-muted-foreground/80" />
                    {user.phone_e164}
                  </span>
                )}
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-muted-foreground/80" />
                  Africa/Kigali (UTC+2)
                </span>
              </div>

              <div className="pt-2 flex flex-wrap items-center justify-center sm:justify-start gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploadingAvatar}
                  className="h-7 text-xs"
                >
                  <Camera className="w-3.5 h-3.5 mr-1.5" />
                  {isUploadingAvatar ? "Uploading..." : "Upload Photo"}
                </Button>
                {user.avatar_url && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={handleRemoveAvatar}
                    disabled={isUploadingAvatar}
                    className="h-7 text-xs text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                    Remove Photo
                  </Button>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Personal Profile & Organization */}
        <div className="lg:col-span-2 space-y-6">
          {/* Personal Information Form */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <User className="w-4 h-4 text-primary" />
                Personal Profile
              </CardTitle>
              <CardDescription>
                Update your display name, official contact phone number, and dashboard language.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileSave} className="space-y-4">
                {profileSuccess && (
                  <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                    <span>{profileSuccess}</span>
                  </div>
                )}
                {profileError && (
                  <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive border border-destructive/20">
                    <AlertCircle className="w-4 h-4 shrink-0 text-destructive" />
                    <span>{profileError}</span>
                  </div>
                )}

                <div className="space-y-1.5">
                  <Label htmlFor="full_name" className="text-xs">
                    Full Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="full_name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Jean Paul Habimana"
                    required
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="email" className="text-xs">
                      Email Address
                    </Label>
                    <Input
                      id="email"
                      value={user.email || ""}
                      disabled
                      className="bg-muted/50 cursor-not-allowed opacity-80"
                    />
                    <p className="text-[11px] text-muted-foreground">
                      Managed by system administrator.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="phone_e164" className="text-xs">
                      Phone Number (E.164)
                    </Label>
                    <Input
                      id="phone_e164"
                      value={phoneE164}
                      onChange={(e) => setPhoneE164(e.target.value)}
                      placeholder="+250788123456"
                    />
                    <p className="text-[11px] text-muted-foreground">
                      Used for SMS alerts and USSD login.
                    </p>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="language" className="text-xs">
                    Interface Language Preference
                  </Label>
                  <select
                    id="language"
                    value={language}
                    onChange={(e) =>
                      setLanguage(e.target.value as "rw" | "en" | "fr")
                    }
                    className="w-full h-8 px-2.5 py-1 text-xs rounded-md border border-input bg-input/20 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 transition-colors"
                  >
                    <option value="rw">Ikinyarwanda (Rwanda)</option>
                    <option value="en">English (Official)</option>
                    <option value="fr">Français (French)</option>
                  </select>
                </div>

                <div className="pt-2 flex justify-end">
                  <Button
                    type="submit"
                    disabled={isSavingProfile}
                    className="h-8 text-xs px-4"
                  >
                    {isSavingProfile ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      "Save Profile"
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Organizational Assignment Card */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Building2 className="w-4 h-4 text-primary" />
                Organization & Geographic Scope
              </CardTitle>
              <CardDescription>
                Your system role and administrative assignment within the Rwandan educational hierarchy.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-lg border bg-muted/20 space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider block">
                    School Assignment
                  </span>
                  <span className="text-sm font-semibold text-foreground">
                    {user.school_name || (
                      <span className="text-muted-foreground text-xs italic">
                        Not tied to specific school
                      </span>
                    )}
                  </span>
                </div>

                <div className="p-3 rounded-lg border bg-muted/20 space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider block">
                    Sector Scope
                  </span>
                  <span className="text-sm font-semibold text-foreground">
                    {user.sector_name || (
                      <span className="text-muted-foreground text-xs italic">
                        District or National
                      </span>
                    )}
                  </span>
                </div>

                <div className="p-3 rounded-lg border bg-muted/20 space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider block">
                    District Scope
                  </span>
                  <span className="text-sm font-semibold text-foreground">
                    {user.district_name || (
                      <span className="text-muted-foreground text-xs italic">
                        National Level
                      </span>
                    )}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between p-3 rounded-lg border bg-card text-xs">
                <div className="flex items-center gap-2">
                  <Hash className="w-3.5 h-3.5 text-muted-foreground" />
                  <span className="text-muted-foreground">User ID:</span>
                  <code className="font-mono text-[11px] bg-muted px-1.5 py-0.5 rounded">
                    {user.id}
                  </code>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyId}
                  className="h-6 px-2 text-[11px]"
                >
                  {copiedId ? (
                    <>
                      <Check className="w-3 h-3 mr-1 text-emerald-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3 mr-1" />
                      Copy ID
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Security Credentials */}
        <div className="space-y-6">
          {/* Change Password Card */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Lock className="w-4 h-4 text-primary" />
                Web Password
              </CardTitle>
              <CardDescription>
                Update your login password for the Garuka web application.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePasswordChange} className="space-y-3.5">
                {passwordSuccess && (
                  <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                    <span>{passwordSuccess}</span>
                  </div>
                )}
                {passwordError && (
                  <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive border border-destructive/20">
                    <AlertCircle className="w-4 h-4 shrink-0 text-destructive" />
                    <span>{passwordError}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <Label htmlFor="curr_pass" className="text-xs">
                    Current Password
                  </Label>
                  <Input
                    id="curr_pass"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="new_pass" className="text-xs">
                    New Password
                  </Label>
                  <Input
                    id="new_pass"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Min 8 characters"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="conf_pass" className="text-xs">
                    Confirm New Password
                  </Label>
                  <Input
                    id="conf_pass"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                  />
                </div>

                <div className="pt-2">
                  <Button
                    type="submit"
                    disabled={isChangingPassword}
                    className="w-full h-8 text-xs"
                  >
                    {isChangingPassword ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        Updating...
                      </>
                    ) : (
                      "Update Password"
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Change USSD PIN Card */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-primary" />
                USSD Mobile PIN
              </CardTitle>
              <CardDescription>
                4-digit PIN used for attendance and mentor visits on feature phones (*384*1234#).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handlePinChange} className="space-y-3.5">
                {pinSuccess && (
                  <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                    <span>{pinSuccess}</span>
                  </div>
                )}
                {pinError && (
                  <div className="flex items-center gap-2 p-3 text-xs rounded-md bg-destructive/10 text-destructive border border-destructive/20">
                    <AlertCircle className="w-4 h-4 shrink-0 text-destructive" />
                    <span>{pinError}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <Label htmlFor="curr_pin" className="text-xs">
                    Current PIN (leave blank if first time)
                  </Label>
                  <Input
                    id="curr_pin"
                    type="password"
                    inputMode="numeric"
                    maxLength={4}
                    value={currentPin}
                    onChange={(e) =>
                      setCurrentPin(e.target.value.replace(/\D/g, ""))
                    }
                    placeholder="4 digits"
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="new_pin" className="text-xs">
                    New 4-Digit PIN
                  </Label>
                  <Input
                    id="new_pin"
                    type="password"
                    inputMode="numeric"
                    maxLength={4}
                    value={newPin}
                    onChange={(e) =>
                      setNewPin(e.target.value.replace(/\D/g, ""))
                    }
                    placeholder="e.g. 1234"
                    required
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="conf_pin" className="text-xs">
                    Confirm 4-Digit PIN
                  </Label>
                  <Input
                    id="conf_pin"
                    type="password"
                    inputMode="numeric"
                    maxLength={4}
                    value={confirmPin}
                    onChange={(e) =>
                      setConfirmPin(e.target.value.replace(/\D/g, ""))
                    }
                    placeholder="e.g. 1234"
                    required
                  />
                </div>

                <div className="pt-2">
                  <Button
                    type="submit"
                    disabled={isChangingPin}
                    className="w-full h-8 text-xs"
                  >
                    {isChangingPin ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        Updating PIN...
                      </>
                    ) : (
                      "Update USSD PIN"
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
