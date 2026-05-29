package com.project.model;

public class Paper {
    private String id;
    private String title;
    private String authors;
    private String journal;
    private int year;
    private String abstractText;
    private String url;
    private String source; // RISS, KCI, etc.

    public Paper() {}

    public Paper(String id, String title, String authors, String journal,
                 int year, String abstractText, String url, String source) {
        this.id = id;
        this.title = title;
        this.authors = authors;
        this.journal = journal;
        this.year = year;
        this.abstractText = abstractText;
        this.url = url;
        this.source = source;
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getAuthors() { return authors; }
    public void setAuthors(String authors) { this.authors = authors; }

    public String getJournal() { return journal; }
    public void setJournal(String journal) { this.journal = journal; }

    public int getYear() { return year; }
    public void setYear(int year) { this.year = year; }

    public String getAbstractText() { return abstractText; }
    public void setAbstractText(String abstractText) { this.abstractText = abstractText; }

    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
}
