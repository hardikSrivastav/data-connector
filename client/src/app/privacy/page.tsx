"use client";

import { motion } from "framer-motion";

export default function PrivacyPolicy() {
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
            Privacy Policy
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
            <h2 className="text-2xl font-bold mb-4">Introduction</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              Ceneca ("we", "our", or "us") respects your privacy and is committed to protecting your personal data. This privacy policy will inform you about how we look after your personal data when you visit our website and tell you about your privacy rights and how the law protects you.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">The Data We Collect About You</h2>
            <p className="mb-4 text-muted-foreground leading-relaxed">
              Personal data, or personal information, means any information about an individual from which that person can be identified. It does not include data where the identity has been removed (anonymous data).
            </p>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              We may collect, use, store and transfer different kinds of personal data about you which we have grouped together as follows:
            </p>
            <ul className="list-disc pl-6 mb-6 space-y-2 text-muted-foreground">
              <li>Identity Data includes first name, last name, username or similar identifier.</li>
              <li>Contact Data includes email address and telephone numbers.</li>
              <li>Technical Data includes internet protocol (IP) address, your login data, browser type and version, time zone setting and location, browser plug-in types and versions, operating system and platform, and other technology on the devices you use to access this website.</li>
              <li>Usage Data includes information about how you use our website and services.</li>
              <li>Marketing and Communications Data includes your preferences in receiving marketing from us and our third parties and your communication preferences.</li>
            </ul>

            <h2 className="text-2xl font-bold mb-4 mt-10">How We Use Your Personal Data</h2>
            <p className="mb-4 text-muted-foreground leading-relaxed">
              We will only use your personal data when the law allows us to. Most commonly, we will use your personal data in the following circumstances:
            </p>
            <ul className="list-disc pl-6 mb-6 space-y-2 text-muted-foreground">
              <li>Where we need to perform the contract we are about to enter into or have entered into with you.</li>
              <li>Where it is necessary for our legitimate interests (or those of a third party) and your interests and fundamental rights do not override those interests.</li>
              <li>Where we need to comply with a legal obligation.</li>
            </ul>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              Generally, we do not rely on consent as a legal basis for processing your personal data although we will get your consent before sending third party direct marketing communications to you via email or text message. You have the right to withdraw consent to marketing at any time by contacting us.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">Data Security</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              We have put in place appropriate security measures to prevent your personal data from being accidentally lost, used or accessed in an unauthorized way, altered or disclosed. In addition, we limit access to your personal data to those employees, agents, contractors and other third parties who have a business need to know. They will only process your personal data on our instructions and they are subject to a duty of confidentiality.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">Your Legal Rights</h2>
            <p className="mb-4 text-muted-foreground leading-relaxed">
              Under certain circumstances, you have rights under data protection laws in relation to your personal data, including the right to:
            </p>
            <ul className="list-disc pl-6 mb-6 space-y-2 text-muted-foreground">
              <li>Request access to your personal data.</li>
              <li>Request correction of your personal data.</li>
              <li>Request erasure of your personal data.</li>
              <li>Object to processing of your personal data.</li>
              <li>Request restriction of processing your personal data.</li>
              <li>Request transfer of your personal data.</li>
              <li>Right to withdraw consent.</li>
            </ul>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              If you wish to exercise any of the rights set out above, please contact us at privacy@ceneca.com.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">Changes to This Privacy Policy</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              We may update our privacy policy from time to time. We will notify you of any changes by posting the new privacy policy on this page and updating the "Last updated" date at the top of this privacy policy.
            </p>

            <h2 className="text-2xl font-bold mb-4 mt-10">Contact Us</h2>
            <p className="mb-6 text-muted-foreground leading-relaxed">
              If you have any questions about this privacy policy or our privacy practices, please contact us at:
            </p>
            <p className="text-muted-foreground leading-relaxed">
              Email: privacy@ceneca.com<br />
              Phone: +1 (555) 123-4567<br />
              Address: 123 Tech Street, San Francisco, CA 94105
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
} 