import { supabase } from "./supabase";

const BUCKET = "ticket-attachments";

export async function uploadTicketAttachment(ticketId: string, file: File): Promise<string> {
  const ext = file.name.includes(".") ? file.name.split(".").pop() : "png";
  const path = `${ticketId}/${crypto.randomUUID()}.${ext}`;

  const { error } = await supabase.storage.from(BUCKET).upload(path, file, {
    contentType: file.type || "application/octet-stream",
  });
  if (error) throw error;

  const { data } = supabase.storage.from(BUCKET).getPublicUrl(path);
  return data.publicUrl;
}
