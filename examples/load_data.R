# Run from repository root. Keep identifiers as strings; JSON cells stay encoded.
args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args)) args[[1]] else "data/releases/1.0.0"
works <- read.csv(file.path(root, "works.csv"), colClasses = "character",
                  na.strings = "", fileEncoding = "UTF-8")
works$publication_year <- as.integer(works$publication_year)
works$sampling_weight <- as.numeric(works$sampling_weight)
print(table(works$publication_year))
