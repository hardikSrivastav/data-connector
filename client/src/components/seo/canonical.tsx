import Head from 'next/head';
import { usePathname } from 'next/navigation';
import { siteConfig } from '@/lib/constants';

interface CanonicalProps {
  path?: string;
}

export function Canonical({ path }: CanonicalProps) {
  const pathname = usePathname();
  const canonicalUrl = `${siteConfig.url}${path || pathname}`;

  return (
    <Head>
      <link rel="canonical" href={canonicalUrl} />
    </Head>
  );
} 