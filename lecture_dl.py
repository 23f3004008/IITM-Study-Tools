import json
import os
import subprocess
import re
import argparse
import glob
import webvtt
import mistletoe
from weasyprint import HTML
import concurrent.futures
import logging
import multiprocessing

def clean_title(title):
    # Remove prefix like "1.1 " or "L6.1 "
    title = re.sub(r'^\d+\.\d+\s+', '', title)
    title = re.sub(r'^L\d+\.\d+\s+', '', title)
    # Replace spaces with _
    title = title.replace(' ', '_')
    # Remove periods and other punctuation
    title = re.sub(r'[^\w_]', '', title)
    return title

def convert_md_to_pdf(md_path):
    pdf_path = md_path.replace('.md', '.pdf')
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        html_content = mistletoe.markdown(md_content)
        HTML(string=html_content).write_pdf(pdf_path)
        logging.info(f"Created PDF: {os.path.basename(pdf_path)}")
    except Exception as e:
        logging.error(f"Failed to create PDF for {os.path.basename(md_path)}: {e}")

def convert_worker(queue, args):
    while True:
        md_path = queue.get()
        if md_path is None:
            break
        if args.pdf:
            convert_md_to_pdf(md_path)
        if args.txt:
            convert_md_to_txt(md_path)

def convert_md_to_txt(md_path):
    txt_path = md_path.replace('.md', '.txt')
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # For TXT, keep the content as is, since transcripts are plain text
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Created TXT: {os.path.basename(txt_path)}")
    except Exception as e:
        logging.error(f"Failed to create TXT for {os.path.basename(md_path)}: {e}")

def extract_transcript(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        # Download vtt to temp file
        temp_file = f"temp_{video_id}"
        subprocess.run(["yt-dlp", "--write-subs", "--write-auto-subs", "--sub-lang", "en", "--skip-download", "-o", temp_file, url], check=True, capture_output=True, text=True)
        files = glob.glob(temp_file + "*.vtt")
        if not files:
            return None
        vtt_file = files[0]
        vtt = webvtt.read(vtt_file)
        text = []
        for caption in vtt:
            line = caption.text.strip()
            # Remove [Music], [Laughter], etc.
            line = re.sub(r'\[.*?\]', '', line)
            # Skip lines with markup (timed words)
            if '<' in line or '>' in line:
                continue
            if line:
                # Split on newlines and add each subline
                sublines = line.split('\n')
                for subline in sublines:
                    subline = subline.strip()
                    if subline:
                        text.append(subline)
        # Remove consecutive duplicates
        deduped = []
        prev = None
        for line in text:
            if line != prev:
                deduped.append(line)
                prev = line
        text = deduped
        transcript = ' '.join(text)
        # Clean up multiple spaces
        transcript = re.sub(r'\s+', ' ', transcript).strip()
        os.remove(vtt_file)
        return transcript
    except (subprocess.CalledProcessError, Exception):
        return None

def main():
    parser = argparse.ArgumentParser(description='Process lecture data and download transcripts.')
    parser.add_argument('--folders', action='store_true', help='Create subfolders for each week')
    parser.add_argument('--master-weekly', action='store_true', help='Create master MD files for each week')
    parser.add_argument('--master-all', action='store_true', help='Create a master MD file for the entire course')
    parser.add_argument('--md', action='store_true', help='Keep MD files')
    parser.add_argument('--pdf', action='store_true', help='Create PDF files')
    parser.add_argument('--txt', action='store_true', help='Create TXT files')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    # Set up logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')

    # Default to MD if no format specified
    if not args.md and not args.pdf and not args.txt:
        args.md = True

    logging.info("Starting lecture data processing")
    with open('data.json', 'r') as f:
        data = json.load(f)

    namespace = data['namespace']
    folder_name = namespace.replace('ns_', '')
    logging.info(f"Processing course: {folder_name}")
    os.makedirs(folder_name, exist_ok=True)

    outline = data['outline']

    # Collect all lectures
    all_lectures = []
    result = {}
    for unit in outline:
        title = unit['title']
        if title.startswith('Week '):
            children = unit['children']
            sorted_children = sorted(children, key=lambda c: c['id'])
            lectures = []
            for child in sorted_children:
                if child.get('type') == 'L' and child.get('video_type') == 'youtube':
                    lecture = {
                        'title': child['title'],
                        'video_id': child['video'],
                        'youtube_link': f'https://www.youtube.com/watch?v={child["video"]}',
                        'file_path': '',
                        'week': title
                    }
                    lectures.append(lecture)
                    all_lectures.append(lecture)
            result[title] = lectures

    # Set up queue and worker processes for conversions
    conversion_queue = None
    workers = []
    if args.pdf or args.txt:
        conversion_queue = multiprocessing.Queue()
        for _ in range(8):
            p = multiprocessing.Process(target=convert_worker, args=(conversion_queue, args))
            p.start()
            workers.append(p)

    # Process each week
    for week, lectures in result.items():
        logging.info(f"Processing {week}")
        if args.folders:
            week_folder = os.path.join(folder_name, week.replace(' ', '_'))
            os.makedirs(week_folder, exist_ok=True)
        else:
            week_folder = folder_name
        week_num = week.split()[-1]

        # Download transcripts for the week and submit conversions
        for i, lecture in enumerate(lectures):
            lecture_num = i + 1
            clean_name = clean_title(lecture['title'])
            transcript = extract_transcript(lecture['video_id'])
            if transcript:
                file_name = f"Week{week_num}_{lecture_num}_{clean_name}.md"
                md_file = os.path.join(week_folder, file_name)
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(f"# {lecture['title']}\n\n")
                    f.write(transcript)
                lecture['file_path'] = os.path.relpath(md_file, folder_name)
                logging.info(f"Downloaded transcript for {lecture['title']}")

                # Submit conversions immediately
                if conversion_queue:
                    conversion_queue.put(md_file)
            else:
                logging.warning(f"Could not get transcript for {lecture['title']}")

        # Create weekly master after downloads
        if args.master_weekly:
            master_content = f"# {week}\n\n"
            for lecture in lectures:
                if lecture['file_path']:
                    md_file = os.path.join(folder_name, lecture['file_path'])
                    try:
                        with open(md_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        master_content += content + "\n\n---\n\n"
                    except FileNotFoundError:
                        pass
            master_file = os.path.join(week_folder, f"{week.replace(' ', '_')}_master.md")
            with open(master_file, 'w', encoding='utf-8') as f:
                f.write(master_content)
            logging.info(f"Created master file for {week}")
            if conversion_queue:
                conversion_queue.put(master_file)

    # Create master all after all weeks
    if args.master_all:
        master_content = "# Master Transcript\n\n"
        for week, lectures in result.items():
            master_content += f"## {week}\n\n"
            for lecture in lectures:
                if lecture['file_path']:
                    md_file = os.path.join(folder_name, lecture['file_path'])
                    try:
                        with open(md_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        master_content += content + "\n\n---\n\n"
                    except FileNotFoundError:
                        pass
        master_file = os.path.join(folder_name, "all_master.md")
        with open(master_file, 'w', encoding='utf-8') as f:
            f.write(master_content)
        logging.info("Created master file for all")
        if conversion_queue:
            conversion_queue.put(master_file)

    # Wait for all conversions to complete
    if conversion_queue:
        for _ in workers:
            conversion_queue.put(None)
        for p in workers:
            p.join()

    # Update JSON with file_paths
    with open(os.path.join(folder_name, 'youtube_links.json'), 'w') as f:
        json.dump(result, f, indent=4)

    # Remove MD files if not keeping
    if not args.md:
        for root, dirs, files in os.walk(folder_name):
            for file in files:
                if file.endswith('.md'):
                    md_path = os.path.join(root, file)
                    try:
                        os.remove(md_path)
                        logging.info(f"Removed MD: {os.path.basename(md_path)}")
                    except Exception as e:
                        logging.error(f"Failed to remove {os.path.basename(md_path)}: {e}")

    # Update file_paths in result based on formats
    for week, lectures in result.items():
        for lecture in lectures:
            if lecture['file_path']:
                if args.md:
                    pass  # keep .md
                elif args.pdf:
                    lecture['file_path'] = lecture['file_path'].replace('.md', '.pdf')
                elif args.txt:
                    lecture['file_path'] = lecture['file_path'].replace('.md', '.txt')
                # If multiple, prioritize PDF over TXT
                # If both, keep .md, but since removed if not md, but wait, if both pdf and md, keep md, but path is md.
                # But to keep simple, if md, keep .md, else change to the format.

    file_types = []
    if args.md:
        file_types.append("MD")
    if args.pdf:
        file_types.append("PDF")
    if args.txt:
        file_types.append("TXT")
    file_type_str = " and ".join(file_types) if file_types else "transcripts"
    logging.info(f"Created folder {folder_name} with youtube_links.json and {file_type_str}")

if __name__ == "__main__":
    main()
