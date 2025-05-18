import { StructuredData } from './structured-data';
import Script from 'next/script';

export function RootSEO() {
  return (
    <>
      {/* Base structured data */}
      <StructuredData type="website" />
    </>
  );
} 