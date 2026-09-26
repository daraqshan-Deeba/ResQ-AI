"use client";

import type { MouseEvent } from "react";
import { openPhoneDialer, toTelHref } from "@/lib/phone";

export function CallNumberButton({
  phone,
  label,
  className,
}: {
  phone: string;
  label: string;
  className?: string;
}) {
  const href = toTelHref(phone);
  if (!href) return null;

  function dial(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    event.stopPropagation();
    openPhoneDialer(phone);
  }

  return (
    <a
      href={href}
      onClick={dial}
      className={className}
    >
      {label}
    </a>
  );
}
