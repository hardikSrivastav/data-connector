import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

declare global {
  interface Window {
    Razorpay: any;
  }
}

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
  userDetails: {
    name: string;
    email: string;
    company: string;
  };
}

export default function PaymentModal({ isOpen, onClose, userId, userDetails }: PaymentModalProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setIsMounted(true);
    
    // Load Razorpay script
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    document.body.appendChild(script);

    return () => {
      if (script.parentNode) {
        document.body.removeChild(script);
      }
    };
  }, []);

  const handlePayment = async () => {
    if (!userId) {
      toast.error("Unable to process payment. Please try registering again.");
      onClose();
      return;
    }

    setIsLoading(true);

    try {
      // Create order
      const orderResponse = await fetch('/api/payments/create-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ userId }),
      });

      const orderData = await orderResponse.json();
      
      if (!orderData.success) {
        throw new Error(orderData.message || 'Could not create payment order');
      }

      // Initialize Razorpay
      const options = {
        key: orderData.data.keyId,
        amount: orderData.data.amount,
        currency: orderData.data.currency,
        name: "Ceneca",
        description: "Waitlist Registration Fee",
        order_id: orderData.data.orderId,
        handler: function (response: any) {
          handlePaymentSuccess(response);
        },
        prefill: {
          name: userDetails.name,
          email: userDetails.email,
          contact: ""
        },
        notes: {
          address: userDetails.company
        },
        theme: {
          color: "#7b35b8"
        }
      };

      const razorpayInstance = new window.Razorpay(options);
      razorpayInstance.open();
      razorpayInstance.on('payment.failed', function (response: any) {
        toast.error("Payment failed. Please try again.");
        setIsLoading(false);
      });
    } catch (error) {
      console.error("Payment initialization error:", error);
      toast.error("Could not initialize payment. Please try again.");
      setIsLoading(false);
    }
  };

  const handlePaymentSuccess = async (response: any) => {
    try {
      // Verify payment with backend
      const verifyResponse = await fetch('/api/payments/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          razorpayOrderId: response.razorpay_order_id,
          razorpayPaymentId: response.razorpay_payment_id,
          razorpaySignature: response.razorpay_signature,
          userId: userId // Include userId to make sure we connect payment to right user
        }),
      });

      const verifyData = await verifyResponse.json();
      
      if (verifyData.success) {
        toast.success("Payment successful! You've been added to our waitlist.");
        onClose();
        // Signal to the parent component that payment was successful
        window.dispatchEvent(new CustomEvent('payment_success'));
      } else {
        toast.error("Payment verification failed. Please contact support.");
      }
    } catch (error) {
      console.error("Payment verification error:", error);
      toast.error("Payment verification failed. Please contact support.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isMounted || !isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* No overlay background at all */}
      <div className="relative bg-card/50 backdrop-blur-sm border border-muted rounded-xl shadow-xl max-w-md w-full p-6">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
        >
          <X size={20} />
          <span className="sr-only">Close</span>
        </button>
        
        <div className="flex flex-col gap-2 text-center sm:text-left mb-4">
          <h2 className="text-2xl font-bold font-baskerville">Complete Your Registration</h2>
          <p className="text-base text-muted-foreground font-baskerville">
            A one-time payment of ₹375 (approx. $5) is required to join our waitlist.
          </p>
        </div>
        
        <div className="space-y-4 py-4">
          <div className="rounded-lg bg-background/60 p-4 border border-muted">
            <h3 className="font-medium mb-2 font-baskerville">Waitlist Benefits</h3>
            <ul className="space-y-2 text-sm">
              <li className="flex items-start">
                <span className="mr-2 font-baskerville">✓</span>
                <span className="font-baskerville">First month free</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2 font-baskerville">✓</span>
                <span className="font-baskerville">Personalised onboarding</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2 font-baskerville">✓</span>
                <span className="font-baskerville">Direct feedback channel</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2 font-baskerville">✓</span>
                <span className="font-baskerville">Exclusive product development updates</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2 font-baskerville">✓</span>
                <span className="font-baskerville">Early access to our platform</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            onClick={handlePayment}
            disabled={isLoading}
            className="w-full h-10 text-base text-white bg-zinc-900 hover:bg-[#7b35b8] transition-all duration-300 font-baskerville"
          >
            {isLoading ? "Processing..." : "Pay ₹375 to Join Waitlist"}
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
} 