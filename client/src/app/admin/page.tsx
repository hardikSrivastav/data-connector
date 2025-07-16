"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { Shield, Lock, Key } from "lucide-react";

export default function AdminLoginPage() {
  const [showConfirmation, setShowConfirmation] = useState(true);
  const router = useRouter();

  const handleAccess = () => {
    router.push('/admin/dashboard');
  };

  const handleCancel = () => {
    router.push('/');
  };

  if (!showConfirmation) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-background via-background/95 to-muted/10">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Redirecting to dashboard...</p>
        </div>
      </div>
    );
    }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-background via-background/95 to-muted/10">
      <Card className="w-full max-w-md bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center mb-4">
            <Shield className="w-16 h-16 text-primary" />
          </div>
          <CardTitle className="text-2xl font-bold">Admin Access</CardTitle>
          <p className="text-muted-foreground">
            You are about to access the admin dashboard
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="bg-muted/20 p-4 rounded-lg border border-muted">
            <div className="flex items-center gap-3 mb-3">
              <Lock className="w-5 h-5 text-amber-500" />
              <span className="font-medium">Admin Area</span>
            </div>
            <p className="text-sm text-muted-foreground">
              This area contains sensitive administrative functions including user management, waitlist control, and blog administration.
            </p>
            </div>
          
          <div className="flex flex-col gap-3">
            <Button
              onClick={handleAccess}
              className="w-full h-12 text-white bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300"
            >
              <Key className="w-4 h-4 mr-2" />
              Yes, Access Admin Dashboard
            </Button>
            <Button
              onClick={handleCancel}
              variant="outline"
              className="w-full h-12"
            >
              Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 