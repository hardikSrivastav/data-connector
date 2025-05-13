"use client";

import { motion } from "framer-motion";

export default function TermsOfService() {
  return (
    <div className="pt-40 pb-20 bg-gradient-to-b from-background via-background/90 to-muted/20">
      <div className="container mx-auto px-4">
        <motion.div 
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-clip-text text-transparent bg-gradient-to-r from-[#FFE1E0] via-[#9d4edd] to-[#ff006e] tracking-tight font-baskerville leading-tight">
            Terms of Service
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto font-baskerville leading-relaxed">
            Last updated: {new Date().toLocaleDateString('en-US', {month: 'long', day: 'numeric', year: 'numeric'})}
          </p>
        </motion.div>

        <motion.div 
          className="max-w-4xl mx-auto font-baskerville bg-card/30 backdrop-blur-sm border border-muted rounded-xl p-10"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="prose prose-invert prose-lg max-w-none">
            <h2 className="text-2xl font-bold mb-4">1. Agreement to Terms</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              These Terms of Service constitute a legally binding agreement made between you and Ceneca ("we," "us," or "our"), concerning your access to and use of our website and services. You agree that by accessing the services, you have read, understood, and agreed to be bound by all of these Terms of Service.
            </p>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              IF YOU DO NOT AGREE WITH ALL OF THESE TERMS OF SERVICE, THEN YOU ARE EXPRESSLY PROHIBITED FROM USING THE SERVICES AND YOU MUST DISCONTINUE USE IMMEDIATELY.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">2. Intellectual Property Rights</h2>
            <p className="mb-4 text-muted-foreground leading-relaxed">
              Unless otherwise indicated, the services and all source code, databases, functionality, software, website designs, audio, video, text, photographs, and graphics on the services and the trademarks, service marks, and logos contained therein are owned or controlled by us or licensed to us, and are protected by copyright and trademark laws and various other intellectual property rights.
            </p>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              Provided that you are eligible to use the services, you are granted a limited license to access and use the services and to download or print a copy of any portion of the content to which you have properly gained access solely for your personal, non-commercial use. We reserve all rights not expressly granted to you in and to the services, the content, and the trademarks.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">3. User Representations</h2>
            <p className="mb-4 text-muted-foreground leading-relaxed">
              By using the services, you represent and warrant that:
            </p>
            <ul className="list-disc pl-6 mb-6 space-y-2 text-muted-foreground">
              <li>All registration information you submit will be true, accurate, current, and complete.</li>
              <li>You will maintain the accuracy of such information and promptly update such registration information as necessary.</li>
              <li>You have the legal capacity and you agree to comply with these Terms of Service.</li>
              <li>You are not a minor in the jurisdiction in which you reside.</li>
              <li>You will not access the services through automated or non-human means, whether through a bot, script, or otherwise.</li>
              <li>You will not use the services for any illegal or unauthorized purpose.</li>
              <li>Your use of the services will not violate any applicable law or regulation.</li>
            </ul>

            <h2 className="text-2xl font-bold mb-4 mt-10">4. Fees and Payment</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              You may be required to purchase or pay a fee to access some of our services. You agree to provide current, complete, and accurate purchase and account information for all purchases made via the services. You further agree to promptly update account and payment information, including email address, payment method, and payment card expiration date, so that we can complete your transactions and contact you as needed.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">5. Cancellation</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              You can cancel your subscription at any time by contacting us using the contact information provided below. Your cancellation will take effect at the end of the current paid term. If you are unsatisfied with our services, please email us at support@ceneca.com.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">6. Prohibited Activities</h2>
            <p className="mb-4 text-muted-foreground leading-relaxed">
              You may not access or use the services for any purpose other than that for which we make the services available. The services may not be used in connection with any commercial endeavors except those that are specifically endorsed or approved by us.
            </p>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              As a user of the services, you agree not to:
            </p>
            <ul className="list-disc pl-6 mb-6 space-y-2 text-muted-foreground">
              <li>Systematically retrieve data or other content from the services to create or compile, directly or indirectly, a collection, compilation, database, or directory without written permission from us.</li>
              <li>Trick, defraud, or mislead us and other users, especially in any attempt to learn sensitive account information such as user passwords.</li>
              <li>Circumvent, disable, or otherwise interfere with security-related features of the services.</li>
              <li>Disparage, tarnish, or otherwise harm, in our opinion, us and/or the services.</li>
              <li>Use any information obtained from the services in order to harass, abuse, or harm another person.</li>
              <li>Make improper use of our support services or submit false reports of abuse or misconduct.</li>
              <li>Use the services in a manner inconsistent with any applicable laws or regulations.</li>
              <li>Engage in unauthorized framing of or linking to the services.</li>
              <li>Upload or transmit (or attempt to upload or to transmit) viruses, Trojan horses, or other material, including excessive use of capital letters and spamming, that interferes with any party's uninterrupted use and enjoyment of the services or modifies, impairs, disrupts, alters, or interferes with the use, features, functions, operation, or maintenance of the services.</li>
              <li>Delete the copyright or other proprietary rights notice from any content.</li>
              <li>Attempt to impersonate another user or person or use the username of another user.</li>
              <li>Upload or transmit (or attempt to upload or to transmit) any material that acts as a passive or active information collection or transmission mechanism.</li>
              <li>Interfere with, disrupt, or create an undue burden on the services or the networks or services connected to the services.</li>
              <li>Harass, annoy, intimidate, or threaten any of our employees or agents engaged in providing any portion of the services to you.</li>
              <li>Attempt to bypass any measures of the services designed to prevent or restrict access to the services, or any portion of the services.</li>
              <li>Copy or adapt the software, including but not limited to Flash, PHP, HTML, JavaScript, or other code.</li>
              <li>Use the services as part of any effort to compete with us or otherwise use the services and/or the content for any revenue-generating endeavor or commercial enterprise.</li>
            </ul>

            <h2 className="text-2xl font-bold mb-4 mt-10">7. Limitation of Liability</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              IN NO EVENT WILL WE OR OUR DIRECTORS, EMPLOYEES, OR AGENTS BE LIABLE TO YOU OR ANY THIRD PARTY FOR ANY DIRECT, INDIRECT, CONSEQUENTIAL, EXEMPLARY, INCIDENTAL, SPECIAL, OR PUNITIVE DAMAGES, INCLUDING LOST PROFIT, LOST REVENUE, LOSS OF DATA, OR OTHER DAMAGES ARISING FROM YOUR USE OF THE SERVICES, EVEN IF WE HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">8. Contact Us</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              In order to resolve a complaint regarding the services or to receive further information regarding use of the services, please contact us at:
            </p>
            <p className="text-muted-foreground leading-relaxed">
              Email: legal@ceneca.com<br />
              Phone: +1 (555) 123-4567<br />
              Address: 123 Tech Street, San Francisco, CA 94105
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
} 