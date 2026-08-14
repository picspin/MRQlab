import type { Metadata } from "next";
import "./style.css";
export const metadata: Metadata = {title:"MRQLab — From spin to pixel", description:"Teaching MRI simulator"};
export default function Layout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html> }
