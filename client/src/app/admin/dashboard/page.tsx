"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

interface User {
  id: string;
  name: string;
  email: string;
  company: string;
  createdAt: string;
}

interface Payment {
  userId: string;
  status: string;
  amount: number;
  paymentDate: string;
}

interface WaitlistEntry {
  id: string;
  position: number;
  status: string;
  notes: string;
  createdAt: string;
  user: User;
  payment: Payment | null;
}

export default function AdminDashboardPage() {
  const [waitlist, setWaitlist] = useState<WaitlistEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedEntry, setSelectedEntry] = useState<WaitlistEntry | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    position: 0,
    status: "",
    notes: "",
  });
  const router = useRouter();

  useEffect(() => {
    // Check if token exists
    const token = localStorage.getItem("admin_token");
    if (!token) {
      router.push("/admin");
      return;
    }

    fetchWaitlist();
  }, [router]);

  const fetchWaitlist = async () => {
    setIsLoading(true);
    try {
      const token = localStorage.getItem("admin_token");
      
      const response = await fetch("/api/admin/waitlist", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (data.success) {
        setWaitlist(data.data);
      } else {
        toast.error(data.message || "Failed to fetch waitlist");
        if (response.status === 401) {
          // Unauthorized, redirect to login
          localStorage.removeItem("admin_token");
          router.push("/admin");
        }
      }
    } catch (error) {
      console.error("Error fetching waitlist:", error);
      toast.error("Failed to fetch waitlist. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleEdit = (entry: WaitlistEntry) => {
    setSelectedEntry(entry);
    setFormData({
      position: entry.position,
      status: entry.status,
      notes: entry.notes || "",
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedEntry) return;
    
    try {
      const token = localStorage.getItem("admin_token");
      
      const response = await fetch(`/api/admin/waitlist/${selectedEntry.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      const data = await response.json();

      if (data.success) {
        toast.success("Waitlist entry updated successfully");
        setIsDialogOpen(false);
        fetchWaitlist(); // Refresh the list
      } else {
        toast.error(data.message || "Failed to update waitlist entry");
      }
    } catch (error) {
      console.error("Error updating waitlist entry:", error);
      toast.error("Failed to update waitlist entry. Please try again.");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    router.push("/admin");
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + " " + date.toLocaleTimeString();
  };

  return (
    <div className="p-6 pt-36 bg-gradient-to-b from-background via-background/95 to-muted/10">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Waitlist Admin Dashboard</h1>
          <Button onClick={handleLogout} variant="outline">
            Logout
          </Button>
        </div>

        <Card className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl">
          <CardHeader className="flex flex-row justify-between items-center">
            <CardTitle>Waitlist Entries</CardTitle>
            <Button onClick={fetchWaitlist} disabled={isLoading}>
              {isLoading ? "Loading..." : "Refresh"}
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8">Loading waitlist entries...</div>
            ) : waitlist.length === 0 ? (
              <div className="text-center py-8">No waitlist entries found.</div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Position</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Company</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Payment</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {waitlist.map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell>{entry.position}</TableCell>
                        <TableCell>{entry.user.name}</TableCell>
                        <TableCell>{entry.user.email}</TableCell>
                        <TableCell>{entry.user.company}</TableCell>
                        <TableCell>
                          <span
                            className={`px-2 py-1 rounded-full text-xs ${
                              entry.status === "approved"
                                ? "bg-green-100 text-green-800"
                                : entry.status === "denied"
                                ? "bg-red-100 text-red-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {entry.status}
                          </span>
                        </TableCell>
                        <TableCell>
                          {entry.payment ? (
                            <span
                              className={`px-2 py-1 rounded-full text-xs ${
                                entry.payment.status === "paid"
                                  ? "bg-green-100 text-green-800"
                                  : "bg-amber-100 text-amber-800"
                              }`}
                            >
                              {entry.payment.status}
                            </span>
                          ) : (
                            <span className="px-2 py-1 rounded-full text-xs bg-red-100 text-red-800">
                              none
                            </span>
                          )}
                        </TableCell>
                        <TableCell>{formatDate(entry.createdAt)}</TableCell>
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEdit(entry)}
                          >
                            Edit
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl">
          <DialogHeader>
            <DialogTitle>Edit Waitlist Entry</DialogTitle>
            <DialogDescription>
              Update the position, status, or notes for this waitlist entry.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="space-y-4 pt-4">
            <div className="space-y-2">
              <label htmlFor="position" className="text-sm font-medium">
                Position
              </label>
              <Input
                id="position"
                type="number"
                min="1"
                value={formData.position}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    position: parseInt(e.target.value),
                  })
                }
                className="h-10 bg-background/80 border-muted"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="status" className="text-sm font-medium">
                Status
              </label>
              <Select
                value={formData.status}
                onValueChange={(value) =>
                  setFormData({ ...formData, status: value })
                }
              >
                <SelectTrigger id="status" className="h-10 bg-background/80 border-muted">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="denied">Denied</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label htmlFor="notes" className="text-sm font-medium">
                Notes
              </label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) =>
                  setFormData({ ...formData, notes: e.target.value })
                }
                className="bg-background/80 border-muted"
                rows={3}
              />
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit">Save Changes</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
} 